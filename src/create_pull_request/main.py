"""
Main orchestration logic for create-pull-request action.

Implements the 10-phase workflow that coordinates all modules to create
or update pull requests for repository changes.
"""

import os
import sys
from pathlib import Path
from typing import Optional

from .models import ActionInputs, ActionOutputs, PROperation
from .git_command_manager import GitCommandManager
from .git_config_helper import GitConfigHelper
from .github_helper import GitHubHelper
from .branch_manager import BranchManager
from .utils import (
    get_input_as_array,
    get_repo_path,
    read_file,
    file_exists,
    strip_org_prefix_from_teams,
    generate_branch_suffix,
)
from .exceptions import (
    CreatePullRequestError,
    ConfigurationError,
    AuthenticationError,
)


def parse_action_inputs() -> ActionInputs:
    """
    Parse GitHub Actions inputs from environment variables.

    Returns:
        ActionInputs with all parsed values

    Raises:
        ConfigurationError: If required inputs are missing or invalid
    """
    # Required inputs
    token = os.environ.get("INPUT_TOKEN", "")
    if not token:
        raise ConfigurationError("token", "Token is required")

    # Repository settings
    path = os.environ.get("INPUT_PATH", ".")
    add_paths = get_input_as_array("add-paths", [])

    # Commit settings
    commit_message = os.environ.get("INPUT_COMMIT-MESSAGE", "")
    committer = os.environ.get("INPUT_COMMITTER", "")
    author = os.environ.get("INPUT_AUTHOR", "")
    signoff = os.environ.get("INPUT_SIGNOFF", "false").lower() == "true"
    sign_commits = os.environ.get("INPUT_SIGN-COMMITS", "false").lower() == "true"

    # Branch settings
    branch = os.environ.get("INPUT_BRANCH", "create-pull-request/patch")
    branch_suffix = os.environ.get("INPUT_BRANCH-SUFFIX", "none")
    base = os.environ.get("INPUT_BASE", "")
    delete_branch = os.environ.get("INPUT_DELETE-BRANCH", "false").lower() == "true"
    push_to_fork = os.environ.get("INPUT_PUSH-TO-FORK", "")

    # Pull request settings
    title = os.environ.get("INPUT_TITLE", "Changes by create-pull-request action")
    body = os.environ.get("INPUT_BODY", "")
    body_path = os.environ.get("INPUT_BODY-PATH", "")
    labels = get_input_as_array("labels", [])
    assignees = get_input_as_array("assignees", [])
    reviewers = get_input_as_array("reviewers", [])
    team_reviewers = get_input_as_array("team-reviewers", [])

    milestone_str = os.environ.get("INPUT_MILESTONE", "0")
    try:
        milestone = int(milestone_str)
    except ValueError:
        milestone = 0

    draft_str = os.environ.get("INPUT_DRAFT", "false").lower()
    draft = draft_str == "true"

    maintainer_can_modify = os.environ.get("INPUT_MAINTAINER-CAN-MODIFY", "true").lower() == "true"

    # Read body from file if body_path specified
    if body_path and file_exists(body_path):
        body = read_file(body_path)

    # Validate body length (GitHub limit is 65536 characters)
    if len(body) > 65536:
        raise ConfigurationError("body", "Body exceeds maximum length of 65536 characters")

    # Strip org prefix from team reviewers
    team_reviewers = strip_org_prefix_from_teams(team_reviewers)

    return ActionInputs(
        token=token,
        path=path,
        add_paths=add_paths,
        commit_message=commit_message,
        committer=committer,
        author=author,
        signoff=signoff,
        sign_commits=sign_commits,
        branch=branch,
        branch_suffix=branch_suffix,
        base=base,
        delete_branch=delete_branch,
        push_to_fork=push_to_fork,
        title=title,
        body=body,
        body_path=body_path,
        labels=labels,
        assignees=assignees,
        reviewers=reviewers,
        team_reviewers=team_reviewers,
        milestone=milestone,
        draft=draft,
        maintainer_can_modify=maintainer_can_modify,
    )


def set_output(name: str, value: str) -> None:
    """
    Set GitHub Actions output.

    Args:
        name: Output name
        value: Output value
    """
    # GitHub Actions output format
    github_output = os.environ.get("GITHUB_OUTPUT")

    if github_output:
        # Write to GITHUB_OUTPUT file
        with open(github_output, "a") as f:
            # Use multiline format for safety
            delimiter = "EOF"
            f.write(f"{name}<<{delimiter}\n")
            f.write(f"{value}\n")
            f.write(f"{delimiter}\n")
    else:
        # Fallback to stdout format (deprecated but works)
        print(f"::set-output name={name}::{value}")


def run() -> None:
    """
    Main entry point for the action.
    Implements 10-phase workflow:
    1. Parse inputs
    2. Initialize git
    3. Save git config state
    4. Configure git for action
    5. Initialize GitHub API
    6. Determine base branch
    7. Create/update branch
    8. Create/update PR
    9. Apply PR metadata
    10. Set outputs and cleanup
    """
    config_helper: Optional[GitConfigHelper] = None
    github_helper: Optional[GitHubHelper] = None

    try:
        print("=== Create Pull Request Action (Python) ===\n")

        # Phase 1: Parse inputs from environment
        print("Phase 1: Parsing inputs...")
        inputs = parse_action_inputs()

        # Apply branch suffix if specified
        if inputs.branch_suffix != "none":
            suffix = generate_branch_suffix(inputs.branch_suffix)
            inputs.branch = f"{inputs.branch}-{suffix}"
            print(f"Branch with suffix: {inputs.branch}")

        # Phase 2: Initialize git repository
        print("\nPhase 2: Initializing git repository...")
        repo_path = get_repo_path(inputs.path)
        git = GitCommandManager(repo_path)

        # Verify git is available
        _, version, _ = git.exec(["--version"])
        print(f"Git version: {version.strip()}")

        # Phase 3: Save git config state
        print("\nPhase 3: Saving git configuration...")
        config_helper = GitConfigHelper(git)
        config_helper.configure(inputs.token)

        # Phase 4: Configure git for action
        print("\nPhase 4: Configuring git identity...")
        # Git identity will be set per-commit in branch manager
        # Here we just verify the repository state
        status = git.status(["--short"])
        if status:
            print(f"Working directory status:\n{status}")

        # Phase 5: Initialize GitHub API helper
        print("\nPhase 5: Initializing GitHub API...")
        repo_full_name = os.environ.get("GITHUB_REPOSITORY", "")
        if not repo_full_name:
            raise ConfigurationError(
                "GITHUB_REPOSITORY",
                "GITHUB_REPOSITORY environment variable not set"
            )

        github_helper = GitHubHelper(inputs.token, repo_full_name)
        print(f"Connected to repository: {repo_full_name}")

        # Phase 6: Determine base branch
        print("\nPhase 6: Determining base branch...")
        if not inputs.base:
            # Use current branch as base
            current_branch = git.get_current_branch()
            if current_branch:
                inputs.base = current_branch
                print(f"Using current branch as base: {inputs.base}")
            else:
                # Detached HEAD - must specify base
                raise ConfigurationError(
                    "base",
                    "Base branch must be specified when in detached HEAD state"
                )
        else:
            print(f"Using specified base: {inputs.base}")

        # Get base SHA
        base_sha = git.rev_parse(inputs.base)
        print(f"Base SHA: {base_sha[:8]}")

        # Phase 7: Create or update branch with changes
        print("\nPhase 7: Creating/updating branch...")
        branch_manager = BranchManager(git, github_helper)
        branch_state = branch_manager.create_or_update_branch(inputs, base_sha)

        print(f"Branch operation: {branch_state.action}")
        print(f"Has diff with base: {branch_state.has_diff_with_base}")
        print(f"Head SHA: {branch_state.head_sha[:8]}")

        # Phase 8: Push branch if needed
        if branch_state.action in ["created", "updated"]:
            print("\nPhase 8: Pushing branch...")

            # Determine remote to push to
            if inputs.push_to_fork:
                print(f"Pushing to fork: {inputs.push_to_fork}")
                fork_remote = branch_manager.configure_fork_push(
                    inputs.push_to_fork,
                    inputs.token
                )
                branch_manager.push_branch(inputs.branch, remote=fork_remote)
            else:
                branch_manager.push_branch(inputs.branch, remote="origin")

            print(f"Branch {inputs.branch} pushed successfully")
        else:
            print("\nPhase 8: No push needed (no changes)")

        # Phase 9: Create or update pull request
        print("\nPhase 9: Creating/updating pull request...")

        pr_operation = PROperation.NONE
        pr_number = None
        pr_url = None

        if branch_state.has_diff_with_base:
            # Create or update PR
            pr = github_helper.create_or_update_pull_request(
                branch=inputs.branch,
                base=inputs.base,
                title=inputs.title,
                body=inputs.body,
                draft=inputs.draft,
                maintainer_can_modify=inputs.maintainer_can_modify
            )

            pr_number = pr.number
            pr_url = pr.html_url
            pr_operation = PROperation.CREATED if branch_state.action == "created" else PROperation.UPDATED

            print(f"Pull request #{pr_number}: {pr_url}")
            print(f"Operation: {pr_operation.value}")

            # Apply PR metadata
            if inputs.labels or inputs.assignees or inputs.reviewers or inputs.team_reviewers or inputs.milestone:
                print("\nApplying PR metadata...")
                github_helper.update_pull_request_metadata(
                    pr_number=pr_number,
                    labels=inputs.labels if inputs.labels else None,
                    assignees=inputs.assignees if inputs.assignees else None,
                    reviewers=inputs.reviewers if inputs.reviewers else None,
                    team_reviewers=inputs.team_reviewers if inputs.team_reviewers else None,
                    milestone=inputs.milestone if inputs.milestone > 0 else None
                )
                print("Metadata applied successfully")

        elif inputs.delete_branch:
            # No diff and delete_branch is true - delete the branch
            print("No changes detected and delete-branch is true")
            try:
                github_helper.delete_branch(inputs.branch)
                print(f"Deleted branch: {inputs.branch}")
                pr_operation = PROperation.CLOSED
            except Exception as e:
                print(f"Could not delete branch: {e}")

        else:
            print("No changes detected, no PR created")

        # Phase 10: Set outputs and cleanup
        print("\nPhase 10: Setting outputs...")

        outputs = ActionOutputs(
            pull_request_number=pr_number,
            pull_request_url=pr_url,
            pull_request_operation=pr_operation.value,
            pull_request_head_sha=branch_state.head_sha,
            pull_request_branch=inputs.branch,
            pull_request_commits_verified=False  # TODO: Implement commit verification
        )

        # Set GitHub Actions outputs
        for key, value in outputs.to_dict().items():
            if value:
                set_output(key, value)

        print("\n=== Action completed successfully ===")

    except AuthenticationError as e:
        print(f"\n❌ Authentication Error: {e}", file=sys.stderr)
        sys.exit(1)

    except ConfigurationError as e:
        print(f"\n❌ Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)

    except CreatePullRequestError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        # Cleanup
        if config_helper:
            try:
                config_helper.restore()
                print("\nGit configuration restored")
            except Exception as e:
                print(f"Warning: Could not restore git config: {e}", file=sys.stderr)

        if github_helper:
            try:
                github_helper.close()
            except Exception:
                pass


if __name__ == "__main__":
    run()
