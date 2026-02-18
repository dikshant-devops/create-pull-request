"""
Git configuration state management.

Handles backup and restoration of git configuration during action execution,
including authentication setup and credential management.
"""

import base64
from typing import Optional
from pathlib import Path

from .git_command_manager import GitCommandManager
from .models import GitConfig, RemoteDetail, GitProtocol
from .utils import parse_remote_url
from .exceptions import ConfigurationError


class GitConfigHelper:
    """
    Manages git configuration state for backup/restore operations.
    Mirrors the TypeScript GitConfigHelper class.
    """

    def __init__(self, git: GitCommandManager):
        """
        Initialize git config helper.

        Args:
            git: GitCommandManager instance
        """
        self.git = git
        self.working_dir = git.working_dir
        self.safe_directory_set = False
        self.persisted_extraheader: Optional[str] = None
        self.remote_url: Optional[str] = None
        self.remote_detail: Optional[RemoteDetail] = None

    def configure(self, token: str) -> None:
        """
        Configure git for action execution.
        Sets up authentication and safe directory.

        Args:
            token: GitHub token for authentication
        """
        # Add safe.directory for current working directory
        try:
            self.git.config(
                "safe.directory",
                str(self.working_dir),
                global_config=True
            )
            self.safe_directory_set = True
        except Exception:
            # Continue if safe.directory fails (might not be needed)
            pass

        # Get remote URL
        try:
            self.remote_url = self.git.get_remote_url("origin")
            self.remote_detail = parse_remote_url(self.remote_url)
        except Exception as e:
            raise ConfigurationError("git-remote", f"Failed to get remote URL: {str(e)}")

        # Configure authentication for HTTPS
        if self.remote_detail.protocol == GitProtocol.HTTPS:
            self._configure_https_auth(token)

    def _configure_https_auth(self, token: str) -> None:
        """
        Configure HTTPS authentication with token.

        Args:
            token: GitHub token
        """
        # Save existing extraheader if present
        remote_url = self.remote_url or ""
        extraheader_key = f"http.{remote_url}/.extraheader"

        existing = self.git.config_get(extraheader_key)
        if existing:
            self.persisted_extraheader = existing

        # Set authorization header with token
        # Format: AUTHORIZATION: basic <base64(x-access-token:TOKEN)>
        auth_string = f"x-access-token:{token}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        header_value = f"AUTHORIZATION: basic {auth_base64}"

        self.git.config(extraheader_key, header_value)

    def restore(self) -> None:
        """
        Restore original git configuration.
        Cleans up authentication and safe directory settings.
        """
        # Remove authorization header
        if self.remote_url and self.remote_detail:
            if self.remote_detail.protocol == GitProtocol.HTTPS:
                extraheader_key = f"http.{self.remote_url}/.extraheader"

                # Try to unset the extraheader we set
                self.git.try_config_unset(extraheader_key)

                # Restore persisted extraheader if it existed
                if self.persisted_extraheader:
                    try:
                        self.git.config(extraheader_key, self.persisted_extraheader)
                    except Exception:
                        pass  # Best effort restore

        # Remove safe.directory
        if self.safe_directory_set:
            try:
                self.git.try_config_unset(
                    "safe.directory",
                    global_config=True
                )
            except Exception:
                pass  # Best effort cleanup

    def configure_identity(self, name: str, email: str) -> None:
        """
        Configure git user identity.

        Args:
            name: User name
            email: User email
        """
        if name:
            self.git.config("user.name", name)
        if email:
            self.git.config("user.email", email)

    def get_remote_detail(self) -> Optional[RemoteDetail]:
        """
        Get parsed remote details.

        Returns:
            RemoteDetail or None if not configured
        """
        return self.remote_detail


class AuthHelper:
    """
    Helper for authentication configuration.
    Provides static methods for auth setup.
    """

    @staticmethod
    def configure_token_auth(
        git: GitCommandManager,
        token: str,
        remote_url: str
    ) -> None:
        """
        Configure token-based authentication.

        Args:
            git: GitCommandManager instance
            token: GitHub token
            remote_url: Git remote URL
        """
        remote_detail = parse_remote_url(remote_url)

        if remote_detail.protocol == GitProtocol.HTTPS:
            # Use extraheader for HTTPS auth
            auth_string = f"x-access-token:{token}"
            auth_base64 = base64.b64encode(auth_string.encode()).decode()
            header_value = f"AUTHORIZATION: basic {auth_base64}"

            extraheader_key = f"http.{remote_url}/.extraheader"
            git.config(extraheader_key, header_value)

        # SSH doesn't need token configuration

    @staticmethod
    def get_authenticated_remote_url(
        remote_detail: RemoteDetail,
        token: Optional[str] = None
    ) -> str:
        """
        Build authenticated remote URL.

        Args:
            remote_detail: Parsed remote details
            token: GitHub token (for HTTPS)

        Returns:
            Remote URL with authentication
        """
        if remote_detail.protocol == GitProtocol.HTTPS and token:
            # Include token in URL for push operations
            return f"https://x-access-token:{token}@{remote_detail.hostname}/{remote_detail.repository}.git"
        elif remote_detail.protocol == GitProtocol.SSH:
            return f"git@{remote_detail.hostname}:{remote_detail.repository}.git"
        elif remote_detail.protocol == GitProtocol.GIT:
            return f"git://{remote_detail.hostname}/{remote_detail.repository}.git"
        else:
            return f"https://{remote_detail.hostname}/{remote_detail.repository}.git"
