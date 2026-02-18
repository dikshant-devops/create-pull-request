"""
Data models for create-pull-request action.

These dataclasses define the structure for inputs, outputs, and internal state
used throughout the action workflow.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import Enum


class GitProtocol(Enum):
    """Git remote URL protocol types."""
    HTTPS = "https"
    SSH = "ssh"
    GIT = "git"


class BranchSuffix(Enum):
    """Branch suffix generation strategies."""
    NONE = "none"
    TIMESTAMP = "timestamp"
    RANDOM = "random"
    SHORT_COMMIT_HASH = "short-commit-hash"


class PROperation(Enum):
    """Pull request operation types."""
    CREATED = "created"
    UPDATED = "updated"
    CLOSED = "closed"
    NONE = "none"


@dataclass
class ActionInputs:
    """
    GitHub Action inputs.
    Maps to all input parameters defined in action.yml.
    """
    # Required
    token: str

    # Repository settings
    path: str = "."
    add_paths: List[str] = field(default_factory=list)

    # Commit settings
    commit_message: str = ""
    committer: str = ""
    author: str = ""
    signoff: bool = False
    sign_commits: bool = False

    # Branch settings
    branch: str = "create-pull-request/patch"
    branch_suffix: str = "none"
    base: str = ""
    delete_branch: bool = False
    push_to_fork: str = ""

    # Pull request settings
    title: str = "Changes by create-pull-request action"
    body: str = ""
    body_path: str = ""
    labels: List[str] = field(default_factory=list)
    assignees: List[str] = field(default_factory=list)
    reviewers: List[str] = field(default_factory=list)
    team_reviewers: List[str] = field(default_factory=list)
    milestone: int = 0
    draft: bool = False
    maintainer_can_modify: bool = True


@dataclass
class GitIdentity:
    """Git user identity (name and email)."""
    name: str
    email: str


@dataclass
class RemoteDetail:
    """Git remote repository details."""
    protocol: GitProtocol
    hostname: str
    repository: str  # owner/repo format


@dataclass
class GitConfig:
    """Git configuration state for backup/restore."""
    safe_directory: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    credential_helper: Optional[str] = None
    extra_header: Optional[str] = None


@dataclass
class FileChange:
    """Represents a file change in a commit."""
    mode: str  # File mode (100644, 100755, etc.)
    status: str  # A (added), M (modified), D (deleted)
    path: str
    dst_sha: Optional[str] = None  # Content SHA


@dataclass
class CommitMetadata:
    """
    Parsed commit information.
    Mirrors the Commit type from TypeScript implementation.
    """
    sha: str
    tree: str
    parents: List[str]
    subject: str
    body: str
    signed: bool = False
    changes: List[FileChange] = field(default_factory=list)
    unparsed_changes: List[str] = field(default_factory=list)


@dataclass
class BranchState:
    """
    State information about a branch operation.
    Returned by branch creation/update operations.
    """
    action: str  # 'created', 'updated', 'not-updated', or 'none'
    base: str  # Base branch name
    base_commit: Optional[CommitMetadata]
    head_sha: str
    has_diff_with_base: bool
    branch_commits: List[CommitMetadata] = field(default_factory=list)


@dataclass
class PullRequestResult:
    """Result of pull request creation or update."""
    number: int
    url: str
    operation: PROperation
    head_sha: str
    branch: str
    commits_verified: bool = False


@dataclass
class ActionOutputs:
    """GitHub Action outputs."""
    pull_request_number: Optional[int] = None
    pull_request_url: Optional[str] = None
    pull_request_operation: str = "none"
    pull_request_head_sha: Optional[str] = None
    pull_request_branch: Optional[str] = None
    pull_request_commits_verified: bool = False

    def to_dict(self) -> Dict[str, str]:
        """Convert outputs to string dictionary for GitHub Actions."""
        return {
            "pull-request-number": str(self.pull_request_number) if self.pull_request_number else "",
            "pull-request-url": self.pull_request_url or "",
            "pull-request-operation": self.pull_request_operation,
            "pull-request-head-sha": self.pull_request_head_sha or "",
            "pull-request-branch": self.pull_request_branch or "",
            "pull-request-commits-verified": str(self.pull_request_commits_verified).lower(),
        }
