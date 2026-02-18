"""
Git command manager for executing git operations.

Provides a high-level interface for git commands with proper error handling,
output capture, and environment management.
"""

import subprocess
import sys
import os
import base64
from typing import List, Optional, Dict, Tuple
from pathlib import Path

from .models import CommitMetadata, FileChange
from .exceptions import GitCommandError
from .utils import parse_git_diff_output


class GitCommandManager:
    """
    Manages git command execution with subprocess.
    Mirrors the TypeScript GitCommandManager class.
    """

    def __init__(self, working_dir: str):
        """
        Initialize git command manager.

        Args:
            working_dir: Working directory for git commands
        """
        self.working_dir = Path(working_dir).resolve()
        self.show_output = os.environ.get("CPR_SHOW_GIT_CMD_OUTPUT", "false").lower() == "true"

    def exec(
        self,
        args: List[str],
        allow_all_exit_codes: bool = False,
        env: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, str]:
        """
        Execute git command.

        Args:
            args: Git command arguments (e.g., ['status', '--short'])
            allow_all_exit_codes: If True, don't raise exception on non-zero exit
            env: Additional environment variables

        Returns:
            Tuple of (exit_code, stdout, stderr)

        Raises:
            GitCommandError: If command fails and allow_all_exit_codes is False
        """
        command = ["git"] + args

        # Build environment
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        # Execute command
        try:
            result = subprocess.run(
                command,
                cwd=str(self.working_dir),
                env=full_env,
                capture_output=True,
                text=True,
            )

            # Show output if debugging enabled
            if self.show_output:
                print(f"[git] {' '.join(args)}")
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)

            # Check exit code
            if result.returncode != 0 and not allow_all_exit_codes:
                raise GitCommandError(
                    command=' '.join(command),
                    exit_code=result.returncode,
                    stderr=result.stderr.strip()
                )

            return result.returncode, result.stdout, result.stderr

        except FileNotFoundError:
            raise GitCommandError(
                command=' '.join(command),
                exit_code=-1,
                stderr="git command not found. Is git installed?"
            )

    def config(self, key: str, value: str, global_config: bool = False) -> None:
        """
        Set git config value.

        Args:
            key: Config key
            value: Config value
            global_config: If True, set global config
        """
        args = ["config"]
        if global_config:
            args.append("--global")
        args.extend([key, value])
        self.exec(args)

    def config_get(self, key: str, global_config: bool = False) -> Optional[str]:
        """
        Get git config value.

        Args:
            key: Config key
            global_config: If True, get global config

        Returns:
            Config value or None if not set
        """
        args = ["config"]
        if global_config:
            args.append("--global")
        args.append(key)

        exit_code, stdout, _ = self.exec(args, allow_all_exit_codes=True)
        if exit_code == 0:
            return stdout.strip()
        return None

    def try_config_unset(self, key: str, global_config: bool = False) -> bool:
        """
        Try to unset git config value.

        Args:
            key: Config key to unset
            global_config: If True, unset global config

        Returns:
            True if config existed and was unset, False otherwise
        """
        args = ["config", "--unset"]
        if global_config:
            args.append("--global")
        args.append(key)

        exit_code, _, _ = self.exec(args, allow_all_exit_codes=True)
        return exit_code == 0

    def checkout(self, ref: str, start_point: Optional[str] = None) -> None:
        """
        Checkout branch or commit.
        Uses -B flag to create or reset branch.

        Args:
            ref: Branch or ref to checkout
            start_point: Starting point for new branch
        """
        args = ["checkout", "-B", ref]
        if start_point:
            args.append(start_point)
        self.exec(args)

    def cherry_pick(
        self,
        commits: List[str],
        strategy: Optional[str] = None,
        strategy_option: Optional[str] = None,
        allow_all_exit_codes: bool = False
    ) -> Tuple[int, str, str]:
        """
        Cherry-pick commits.

        Args:
            commits: List of commit SHAs to cherry-pick
            strategy: Merge strategy (e.g., 'recursive')
            strategy_option: Strategy option (e.g., 'theirs')
            allow_all_exit_codes: Allow all exit codes

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        args = ["cherry-pick"]

        if strategy:
            args.extend(["--strategy", strategy])
        if strategy_option:
            args.extend(["--strategy-option", strategy_option])

        args.extend(commits)

        return self.exec(args, allow_all_exit_codes=allow_all_exit_codes)

    def commit(
        self,
        message: str,
        signoff: bool = False,
        allow_empty: bool = False,
        identity: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Create commit.

        Args:
            message: Commit message
            signoff: Add Signed-off-by line
            allow_empty: Allow empty commits
            identity: Identity dict with 'name' and 'email'
        """
        args = ["commit", "-m", message]

        if signoff:
            args.append("--signoff")
        if allow_empty:
            args.append("--allow-empty")

        # Set identity via environment if provided
        env = {}
        if identity:
            if "name" in identity:
                env["GIT_AUTHOR_NAME"] = identity["name"]
                env["GIT_COMMITTER_NAME"] = identity["name"]
            if "email" in identity:
                env["GIT_AUTHOR_EMAIL"] = identity["email"]
                env["GIT_COMMITTER_EMAIL"] = identity["email"]

        self.exec(args, env=env)

    def fetch(
        self,
        refspec: List[str],
        remote_name: str = "origin",
        options: Optional[List[str]] = None,
        unshallow: bool = False
    ) -> None:
        """
        Fetch from remote.

        Args:
            refspec: Refspecs to fetch (e.g., ['main:main'])
            remote_name: Remote name
            options: Additional fetch options
            unshallow: Convert shallow clone to complete repo
        """
        args = ["fetch"]

        if unshallow:
            args.append("--unshallow")

        if options:
            args.extend(options)

        args.append(remote_name)
        args.extend(refspec)

        self.exec(args)

    def push(
        self,
        remote_name: str = "origin",
        refspec: Optional[str] = None,
        force_with_lease: bool = False,
        set_upstream: bool = False
    ) -> None:
        """
        Push to remote.

        Args:
            remote_name: Remote name
            refspec: Refspec to push (e.g., 'main:main')
            force_with_lease: Use --force-with-lease
            set_upstream: Set upstream with -u
        """
        args = ["push"]

        if force_with_lease:
            args.append("--force-with-lease")
        if set_upstream:
            args.append("-u")

        args.append(remote_name)

        if refspec:
            args.append(refspec)

        self.exec(args)

    def rev_parse(self, ref: str, short: bool = False) -> str:
        """
        Get SHA for ref.

        Args:
            ref: Reference to parse (e.g., 'HEAD', 'main')
            short: Return short SHA

        Returns:
            SHA string
        """
        args = ["rev-parse"]
        if short:
            args.append("--short")
        args.append(ref)

        _, stdout, _ = self.exec(args)
        return stdout.strip()

    def rev_list(
        self,
        expression: str,
        options: Optional[List[str]] = None
    ) -> List[str]:
        """
        List commits.

        Args:
            expression: Rev-list expression (e.g., 'main..HEAD')
            options: Additional options (e.g., ['--reverse'])

        Returns:
            List of commit SHAs
        """
        args = ["rev-list"]
        if options:
            args.extend(options)
        args.append(expression)

        exit_code, stdout, _ = self.exec(args, allow_all_exit_codes=True)

        if exit_code != 0 or not stdout.strip():
            return []

        return [sha.strip() for sha in stdout.strip().split("\n") if sha.strip()]

    def has_diff(self, ref1: Optional[str] = None, ref2: Optional[str] = None) -> bool:
        """
        Check if there's a diff between refs or working tree.

        Args:
            ref1: First ref (optional)
            ref2: Second ref (optional)

        Returns:
            True if diff exists
        """
        args = ["diff", "--quiet"]

        if ref1 and ref2:
            args.append(f"{ref1}..{ref2}")
        elif ref1:
            args.append(ref1)

        exit_code, _, _ = self.exec(args, allow_all_exit_codes=True)
        # Exit code 0 means no diff, 1 means diff exists
        return exit_code == 1

    def is_dirty(self, include_untracked: bool = False, pathspec: Optional[List[str]] = None) -> bool:
        """
        Check if working directory has changes.

        Args:
            include_untracked: Include untracked files
            pathspec: Specific paths to check

        Returns:
            True if working directory is dirty
        """
        args = ["status", "--porcelain"]

        if include_untracked:
            args.append("--untracked-files=normal")
        else:
            args.append("--untracked-files=no")

        if pathspec:
            args.append("--")
            args.extend(pathspec)

        _, stdout, _ = self.exec(args)
        return len(stdout.strip()) > 0

    def status(self, options: Optional[List[str]] = None) -> str:
        """
        Get git status.

        Args:
            options: Additional status options

        Returns:
            Status output
        """
        args = ["status"]
        if options:
            args.extend(options)

        _, stdout, _ = self.exec(args)
        return stdout

    def add(self, paths: Optional[List[str]] = None, all_files: bool = False) -> None:
        """
        Add files to staging area.

        Args:
            paths: Specific paths to add
            all_files: Add all files with -A
        """
        args = ["add"]

        if all_files:
            args.append("-A")
        elif paths:
            args.append("--")
            args.extend(paths)
        else:
            raise ValueError("Either paths or all_files must be specified")

        self.exec(args)

    def stash_push(self, include_untracked: bool = False) -> bool:
        """
        Stash changes.

        Args:
            include_untracked: Include untracked files

        Returns:
            True if stash was created, False if nothing to stash
        """
        args = ["stash", "push"]

        if include_untracked:
            args.append("--include-untracked")

        exit_code, stdout, _ = self.exec(args, allow_all_exit_codes=True)

        # Check if stash was actually created
        return "No local changes to save" not in stdout

    def stash_pop(self) -> None:
        """Pop stashed changes."""
        self.exec(["stash", "pop"])

    def branch_exists_remote(self, branch: str, remote: str = "origin") -> bool:
        """
        Check if branch exists on remote.

        Args:
            branch: Branch name
            remote: Remote name

        Returns:
            True if branch exists on remote
        """
        args = ["ls-remote", "--heads", remote, f"refs/heads/{branch}"]
        _, stdout, _ = self.exec(args)
        return len(stdout.strip()) > 0

    def branch_exists_local(self, branch: str) -> bool:
        """
        Check if branch exists locally.

        Args:
            branch: Branch name

        Returns:
            True if branch exists locally
        """
        exit_code, _, _ = self.exec(
            ["rev-parse", "--verify", f"refs/heads/{branch}"],
            allow_all_exit_codes=True
        )
        return exit_code == 0

    def get_current_branch(self) -> Optional[str]:
        """
        Get current branch name.

        Returns:
            Branch name or None if detached HEAD
        """
        exit_code, stdout, _ = self.exec(
            ["symbolic-ref", "--short", "HEAD"],
            allow_all_exit_codes=True
        )

        if exit_code == 0:
            return stdout.strip()
        return None

    def is_ahead(self, base: str, branch: str) -> bool:
        """
        Check if branch is ahead of base.

        Args:
            base: Base ref
            branch: Branch ref

        Returns:
            True if branch has commits ahead of base
        """
        commits = self.rev_list(f"{base}..{branch}")
        return len(commits) > 0

    def is_behind(self, base: str, branch: str) -> bool:
        """
        Check if branch is behind base.

        Args:
            base: Base ref
            branch: Branch ref

        Returns:
            True if branch is behind base
        """
        commits = self.rev_list(f"{branch}..{base}")
        return len(commits) > 0

    def is_even(self, ref1: str, ref2: str) -> bool:
        """
        Check if two refs point to same commit.

        Args:
            ref1: First ref
            ref2: Second ref

        Returns:
            True if refs are equal
        """
        try:
            sha1 = self.rev_parse(ref1)
            sha2 = self.rev_parse(ref2)
            return sha1 == sha2
        except GitCommandError:
            return False

    def get_commit(self, ref: str) -> CommitMetadata:
        """
        Get detailed commit information.

        Args:
            ref: Commit ref

        Returns:
            CommitMetadata with full commit details
        """
        # Get commit details with custom format
        format_str = "%H%n%T%n%P%n%s%n%b"
        _, stdout, _ = self.exec(["show", "-s", f"--format={format_str}", ref])

        lines = stdout.split("\n")
        sha = lines[0].strip()
        tree = lines[1].strip()
        parents = lines[2].strip().split() if lines[2].strip() else []
        subject = lines[3].strip() if len(lines) > 3 else ""
        body = "\n".join(lines[4:]).strip() if len(lines) > 4 else ""

        # Get file changes
        _, diff_output, _ = self.exec(
            ["diff-tree", "--no-commit-id", "--name-status", "-r", ref]
        )

        changes = []
        for status, path in parse_git_diff_output(diff_output):
            changes.append(FileChange(
                mode="100644",  # Default mode
                status=status,
                path=path
            ))

        return CommitMetadata(
            sha=sha,
            tree=tree,
            parents=parents,
            subject=subject,
            body=body,
            signed=False,  # Would need to check GPG signature
            changes=changes
        )

    def show_file_at_ref(self, ref: str, path: str, as_base64: bool = False) -> str:
        """
        Get file content at specific ref.

        Args:
            ref: Git ref
            path: File path
            as_base64: Return as base64 encoded string

        Returns:
            File content
        """
        _, stdout, _ = self.exec(["show", f"{ref}:{path}"])

        if as_base64:
            return base64.b64encode(stdout.encode()).decode()

        return stdout

    def get_remote_url(self, remote: str = "origin") -> str:
        """
        Get remote URL.

        Args:
            remote: Remote name

        Returns:
            Remote URL
        """
        _, stdout, _ = self.exec(["remote", "get-url", remote])
        return stdout.strip()

    def remote_add(self, name: str, url: str) -> None:
        """
        Add remote.

        Args:
            name: Remote name
            url: Remote URL
        """
        self.exec(["remote", "add", name, url])

    def remote_remove(self, name: str) -> None:
        """
        Remove remote.

        Args:
            name: Remote name
        """
        self.exec(["remote", "remove", name])

    def branch_delete(self, branch: str, force: bool = False) -> None:
        """
        Delete local branch.

        Args:
            branch: Branch name
            force: Force delete with -D
        """
        flag = "-D" if force else "-d"
        self.exec(["branch", flag, branch])
