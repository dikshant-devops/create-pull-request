"""
Branch management for create-pull-request action.

Handles complex branch operations including creation, updates, rebasing,
cherry-picking, and change detection. This is the core logic ported from
the TypeScript create-or-update-branch.ts module.
"""

import uuid
from typing import Optional, List, Tuple
from enum import Enum

from .git_command_manager import GitCommandManager
from .github_helper import GitHubHelper
from .models import (
    ActionInputs,
    BranchState,
    CommitMetadata,
    GitIdentity,
)
from .exceptions import GitCommandError, BranchConflictError
from .utils import parse_display_name_email


class WorkingBaseType(Enum):
    """Type of working base (branch or commit)."""
    BRANCH = "branch"
    COMMIT = "commit"


# Constants from TypeScript implementation
CHERRYPICK_EMPTY = "The previous cherry-pick is now empty"


class BranchManager:
    """
    Manages branch creation and updates with rebase/cherry-pick logic.
    Mirrors the TypeScript branch management implementation.
    """

    def __init__(
        self,
        git: GitCommandManager,
        github: Optional[GitHubHelper] = None
    ):
        """
        Initialize branch manager.

        Args:
            git: GitCommandManager instance
            github: GitHubHelper instance (optional, for signed commits)
        """
        self.git = git
        self.github = github

    def create_or_update_branch(
        self,
        inputs: ActionInputs,
        base_sha: Optional[str] = None
    ) -> BranchState:
        """
        Create or update branch with changes.
        Implements the core algorithm from TypeScript create-or-update-branch.ts.

        This is the most complex function - it handles:
        1. Creating temporary working branch
        2. Committing changes
        3. Rebasing onto target base (with cherry-pick fallback)
        4. Determining if branch needs creation or update
        5. Building commit metadata

        Args:
            inputs: Action inputs
            base_sha: Base commit SHA (optional)

        Returns:
            BranchState with operation results

        Raises:
            BranchConflictError: If conflicts cannot be resolved
            GitCommandError: If git operations fail
        """
        # Get working base
        working_base, working_base_type = self._get_working_base_and_type()

        # Determine base branch
        base = inputs.base if inputs.base else working_base

        # Create temporary branch for working storage
        temp_branch = f"cpr-tmp-{uuid.uuid4().hex[:8]}"
        print(f"Creating temporary branch: {temp_branch}")

        try:
            # Checkout temporary branch from HEAD
            self.git.checkout(temp_branch, "HEAD")

            # Check if there are changes to commit
            has_changes = self.git.is_dirty(
                include_untracked=True,
                pathspec=inputs.add_paths if inputs.add_paths else None
            )

            if has_changes:
                # Stage changes
                if inputs.add_paths:
                    self.git.add(paths=inputs.add_paths)
                else:
                    self.git.add(all_files=True)

                # Get commit identity
                author = self._get_identity(inputs.author, "author")
                committer = self._get_identity(inputs.committer, "committer")

                # Create commit
                message = inputs.commit_message or "Changes by create-pull-request action"

                # Use identity for commit
                identity = {"name": committer.name, "email": committer.email}

                self.git.commit(
                    message=message,
                    signoff=inputs.signoff,
                    identity=identity
                )

                print(f"Created commit on {temp_branch}")

            # Stash any remaining untracked files
            stashed = self.git.stash_push(include_untracked=True)

            # Reset working base if it's a branch
            if working_base_type == WorkingBaseType.BRANCH:
                self.git.checkout(working_base)
                # Try to reset to remote version
                try:
                    self.git.exec(
                        ["reset", "--hard", f"origin/{working_base}"],
                        allow_all_exit_codes=True
                    )
                except GitCommandError:
                    pass  # Continue if remote doesn't exist

            # Handle rebase if working base differs from target base
            if working_base != base:
                print(f"Rebasing from {working_base} onto {base}")
                self._rebase_onto_base(temp_branch, working_base, base)

            # Determine action (created, updated, not-updated, none)
            action, has_diff_with_base = self._determine_branch_action(
                inputs.branch,
                temp_branch,
                base
            )

            # Get branch head SHA
            head_sha = self.git.rev_parse(inputs.branch)

            # Build commit metadata if there's a diff
            base_commit = None
            branch_commits = []

            if has_diff_with_base:
                base_commit = self.git.get_commit(base)
                branch_commits = self._build_branch_commits(base, inputs.branch)

            # Cleanup temporary branch
            try:
                self.git.branch_delete(temp_branch, force=True)
            except GitCommandError:
                pass  # Best effort cleanup

            # Restore working base and stash
            self.git.checkout(working_base)
            if stashed:
                try:
                    self.git.stash_pop()
                except GitCommandError:
                    print("Warning: Could not restore stashed changes")

            return BranchState(
                action=action,
                base=base,
                base_commit=base_commit,
                head_sha=head_sha,
                has_diff_with_base=has_diff_with_base,
                branch_commits=branch_commits
            )

        except Exception as e:
            # Cleanup on error
            try:
                self.git.branch_delete(temp_branch, force=True)
            except:
                pass

            # Try to restore working state
            try:
                self.git.checkout(working_base)
            except:
                pass

            raise

    def _get_working_base_and_type(self) -> Tuple[str, WorkingBaseType]:
        """
        Determine working base (branch or commit) and its type.

        Returns:
            Tuple of (base_name, base_type)
        """
        current_branch = self.git.get_current_branch()

        if current_branch:
            return current_branch, WorkingBaseType.BRANCH
        else:
            # Detached HEAD - get commit SHA
            head_sha = self.git.rev_parse("HEAD")
            return head_sha, WorkingBaseType.COMMIT

    def _get_identity(self, identity_str: str, identity_type: str) -> GitIdentity:
        """
        Parse and return git identity.

        Args:
            identity_str: Identity string (e.g., "Name <email>")
            identity_type: Type for defaults ("author" or "committer")

        Returns:
            GitIdentity
        """
        if identity_str:
            return parse_display_name_email(identity_str)
        else:
            # Use defaults from environment or git config
            if identity_type == "author":
                name = self.git.config_get("user.name") or "github-actions[bot]"
                email = self.git.config_get("user.email") or "github-actions[bot]@users.noreply.github.com"
            else:
                name = "github-actions[bot]"
                email = "github-actions[bot]@users.noreply.github.com"

            return GitIdentity(name=name, email=email)

    def _rebase_onto_base(
        self,
        temp_branch: str,
        working_base: str,
        target_base: str
    ) -> None:
        """
        Rebase commits from temp_branch onto target_base.
        Falls back to cherry-picking if rebase is not possible.

        Args:
            temp_branch: Temporary branch with changes
            working_base: Original working base
            target_base: Target base branch

        Raises:
            BranchConflictError: If cherry-pick encounters unresolvable conflicts
        """
        # Fetch target base
        try:
            self.git.fetch(
                [f"{target_base}:{target_base}"],
                "origin",
                ["--force", "--depth=1"]
            )
        except GitCommandError:
            print(f"Warning: Could not fetch {target_base}, using local version")

        # Checkout target base
        try:
            self.git.checkout(target_base)
        except GitCommandError:
            # If checkout fails, target base might not exist locally
            print(f"Creating local tracking branch for {target_base}")
            self.git.checkout(target_base, f"origin/{target_base}")

        # Get commits to cherry-pick
        commits = self.git.rev_list(
            f"{working_base}..{temp_branch}",
            options=["--reverse"]
        )

        if not commits:
            print("No commits to cherry-pick")
            # Create branch from current point
            self.git.checkout(temp_branch, target_base)
            return

        print(f"Cherry-picking {len(commits)} commits onto {target_base}")

        # Cherry-pick each commit
        for commit in commits:
            exit_code, stdout, stderr = self.git.cherry_pick(
                [commit],
                strategy="recursive",
                strategy_option="theirs",
                allow_all_exit_codes=True
            )

            # Check if cherry-pick succeeded or commit was empty
            if exit_code != 0:
                if CHERRYPICK_EMPTY in stderr:
                    # Empty commit is okay, skip it
                    print(f"Skipping empty commit: {commit[:8]}")
                    # Abort the cherry-pick
                    self.git.exec(["cherry-pick", "--abort"], allow_all_exit_codes=True)
                    continue
                else:
                    # Real conflict
                    # Abort cherry-pick
                    self.git.exec(["cherry-pick", "--abort"], allow_all_exit_codes=True)
                    raise BranchConflictError(
                        "cherry-pick",
                        f"Failed to cherry-pick commit {commit[:8]}: {stderr}"
                    )

        # Update temp branch to point to current HEAD
        self.git.checkout(temp_branch, "HEAD")

        # Re-fetch base for comparison
        try:
            self.git.fetch(
                [f"{target_base}:{target_base}"],
                "origin",
                ["--force", "--depth=1"]
            )
        except GitCommandError:
            pass

    def _determine_branch_action(
        self,
        branch: str,
        temp_branch: str,
        base: str
    ) -> Tuple[str, bool]:
        """
        Determine what action to take for the branch.

        Returns 'created', 'updated', 'not-updated', or 'none' along with
        whether the branch has a diff with base.

        Args:
            branch: Target branch name
            temp_branch: Temporary branch with changes
            base: Base branch

        Returns:
            Tuple of (action, has_diff_with_base)
        """
        # Check if branch exists remotely
        branch_exists_remote = self.git.branch_exists_remote(branch)

        if not branch_exists_remote:
            # Branch doesn't exist - create it
            print(f"Branch {branch} does not exist remotely, creating...")
            self.git.checkout(branch, temp_branch)

            # Check if branch is ahead of base
            has_diff = self.git.is_ahead(base, branch)

            if has_diff:
                return "created", True
            else:
                return "none", False

        else:
            # Branch exists - check if we need to update it
            print(f"Branch {branch} exists remotely, checking for updates...")

            # Fetch existing branch
            try:
                self.git.fetch([f"{branch}:{branch}"], "origin", ["--force"])
            except GitCommandError:
                print(f"Warning: Could not fetch existing branch {branch}")

            # Checkout existing branch
            self.git.checkout(branch)

            # Count commits ahead in both branches
            branch_commits_ahead = len(self.git.rev_list(f"{base}..{branch}"))
            temp_commits_ahead = len(self.git.rev_list(f"{base}..{temp_branch}"))

            # Check if there's a diff between current branch and temp branch
            has_diff_to_temp = self.git.has_diff(branch, temp_branch)

            # Decide if we should reset the branch
            should_reset = (
                has_diff_to_temp or
                branch_commits_ahead != temp_commits_ahead or
                temp_commits_ahead == 0
            )

            if should_reset:
                print(f"Resetting {branch} to match {temp_branch}")
                self.git.checkout(branch, temp_branch)

            # Check if local branch differs from remote
            needs_push = not self.git.is_even(f"origin/{branch}", branch)

            # Check if branch is ahead of base
            has_diff_with_base = self.git.is_ahead(base, branch)

            if needs_push:
                return "updated", has_diff_with_base
            else:
                return "not-updated", has_diff_with_base

    def _build_branch_commits(
        self,
        base: str,
        branch: str
    ) -> List[CommitMetadata]:
        """
        Build list of commits between base and branch.

        Args:
            base: Base ref
            branch: Branch ref

        Returns:
            List of CommitMetadata
        """
        commit_shas = self.git.rev_list(f"{base}..{branch}")

        commits = []
        for sha in commit_shas:
            try:
                commit = self.git.get_commit(sha)
                commits.append(commit)
            except GitCommandError:
                print(f"Warning: Could not get commit details for {sha}")

        return commits

    def push_branch(
        self,
        branch: str,
        remote: str = "origin",
        force: bool = True
    ) -> None:
        """
        Push branch to remote.

        Args:
            branch: Branch name to push
            remote: Remote name
            force: Use force-with-lease

        Raises:
            GitCommandError: If push fails
        """
        print(f"Pushing {branch} to {remote}")

        self.git.push(
            remote_name=remote,
            refspec=f"{branch}:refs/heads/{branch}",
            force_with_lease=force,
            set_upstream=True
        )

    def configure_fork_push(
        self,
        fork_owner_repo: str,
        token: str
    ) -> str:
        """
        Configure remote for pushing to fork.

        Args:
            fork_owner_repo: Fork repository in owner/repo format
            token: GitHub token

        Returns:
            Remote name for fork

        Raises:
            ConfigurationError: If fork configuration fails
        """
        from .utils import parse_remote_url, get_remote_url

        # Get current remote URL and parse it
        origin_url = self.git.get_remote_url("origin")
        remote_detail = parse_remote_url(origin_url)

        # Build fork URL
        fork_url = get_remote_url(
            remote_detail.protocol,
            remote_detail.hostname,
            fork_owner_repo
        )

        # Add fork remote
        fork_remote = "fork"
        try:
            self.git.remote_add(fork_remote, fork_url)
        except GitCommandError:
            # Remote might already exist, try to update it
            print(f"Fork remote {fork_remote} already exists")

        return fork_remote

    def verify_fork_is_parent(
        self,
        fork_owner_repo: str
    ) -> bool:
        """
        Verify that the fork is actually a fork of the current repository.

        Args:
            fork_owner_repo: Fork repository in owner/repo format

        Returns:
            True if fork relationship is valid

        Raises:
            GitHubAPIError: If verification fails
        """
        if not self.github:
            return True  # Skip verification if GitHub helper not available

        parent = self.github.get_repository_parent()

        if not parent:
            # Current repo is not a fork, can't push to fork
            return False

        return parent.full_name == fork_owner_repo
