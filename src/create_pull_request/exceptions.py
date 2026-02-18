"""
Custom exceptions for create-pull-request action.

These exceptions provide specific error types for different failure scenarios
in the GitHub Action workflow.
"""


class CreatePullRequestError(Exception):
    """Base exception for all create-pull-request errors."""
    pass


class GitCommandError(CreatePullRequestError):
    """Raised when a git command fails."""

    def __init__(self, command: str, exit_code: int, stderr: str):
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(
            f"Git command failed with exit code {exit_code}: {command}\n{stderr}"
        )


class GitHubAPIError(CreatePullRequestError):
    """Raised when a GitHub API call fails."""

    def __init__(self, operation: str, message: str):
        self.operation = operation
        self.message = message
        super().__init__(f"GitHub API error during {operation}: {message}")


class AuthenticationError(CreatePullRequestError):
    """Raised when authentication fails (invalid token, permissions, etc.)."""

    def __init__(self, message: str):
        super().__init__(f"Authentication failed: {message}")


class BranchConflictError(CreatePullRequestError):
    """Raised when a branch operation encounters conflicts."""

    def __init__(self, operation: str, details: str):
        self.operation = operation
        self.details = details
        super().__init__(f"Branch conflict during {operation}: {details}")


class ConfigurationError(CreatePullRequestError):
    """Raised when there's an invalid configuration or input."""

    def __init__(self, parameter: str, message: str):
        self.parameter = parameter
        super().__init__(f"Invalid configuration for '{parameter}': {message}")
