"""
Utility functions for create-pull-request action.

Provides parsing, formatting, and helper functions used across modules.
"""

import re
import os
import uuid
from typing import List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from .models import GitIdentity, GitProtocol, RemoteDetail
from .exceptions import ConfigurationError


def get_input_as_array(name: str, default: Optional[List[str]] = None) -> List[str]:
    """
    Parse GitHub Actions input as array.
    Splits by comma or newline and trims whitespace.

    Args:
        name: Environment variable name (with INPUT_ prefix)
        default: Default value if not set

    Returns:
        List of trimmed strings
    """
    value = os.environ.get(f"INPUT_{name.upper().replace('-', '_')}", "")
    if not value:
        return default or []

    return get_string_as_array(value)


def get_string_as_array(value: str) -> List[str]:
    """
    Split string by comma or newline and trim whitespace.

    Args:
        value: String to split

    Returns:
        List of trimmed non-empty strings
    """
    # Split by comma or newline
    items = re.split(r'[\n,]+', value)
    # Trim whitespace and filter empty strings
    return [item.strip() for item in items if item.strip()]


def parse_display_name_email(value: str) -> GitIdentity:
    """
    Parse git identity from "Display Name <email@address.com>" format.

    Args:
        value: Identity string in format "Name <email>" or just "Name"

    Returns:
        GitIdentity with name and email

    Raises:
        ConfigurationError: If format is invalid
    """
    if not value:
        raise ConfigurationError("identity", "Identity string cannot be empty")

    # Match pattern: "Name <email@domain.com>"
    match = re.match(r'^(.+?)\s*<([^>]+)>$', value.strip())

    if match:
        name = match.group(1).strip()
        email = match.group(2).strip()
        return GitIdentity(name=name, email=email)

    # If no email provided, use the whole string as name with empty email
    # This matches TypeScript behavior for backward compatibility
    return GitIdentity(name=value.strip(), email="")


def generate_branch_suffix(suffix_type: str, git_manager=None) -> str:
    """
    Generate branch name suffix based on type.

    Args:
        suffix_type: Type of suffix (timestamp, random, short-commit-hash, none)
        git_manager: GitCommandManager instance (required for short-commit-hash)

    Returns:
        Generated suffix string
    """
    suffix_type = suffix_type.lower()

    if suffix_type == "none":
        return ""
    elif suffix_type == "timestamp":
        # Return seconds since epoch (10 digits)
        return str(int(datetime.now().timestamp()))
    elif suffix_type == "random":
        # Return 7-character random string
        return str(uuid.uuid4())[:7]
    elif suffix_type == "short-commit-hash":
        if git_manager is None:
            raise ConfigurationError("branch-suffix", "Git manager required for short-commit-hash suffix")
        # Get short commit hash from HEAD
        return git_manager.rev_parse("HEAD", short=True)
    else:
        raise ConfigurationError("branch-suffix", f"Invalid suffix type: {suffix_type}")


def get_remote_url(protocol: GitProtocol, hostname: str, repository: str) -> str:
    """
    Build git remote URL from components.

    Args:
        protocol: Git protocol (HTTPS, SSH, GIT)
        hostname: Git host (e.g., github.com)
        repository: Repository in owner/repo format

    Returns:
        Complete git remote URL
    """
    if protocol == GitProtocol.HTTPS:
        return f"https://{hostname}/{repository}.git"
    elif protocol == GitProtocol.SSH:
        return f"git@{hostname}:{repository}.git"
    elif protocol == GitProtocol.GIT:
        return f"git://{hostname}/{repository}.git"
    else:
        raise ConfigurationError("protocol", f"Unsupported protocol: {protocol}")


def parse_remote_url(url: str) -> RemoteDetail:
    """
    Parse git remote URL to extract protocol, hostname, and repository.

    Supports formats:
    - HTTPS: https://[user@]hostname/owner/repo[.git]
    - SSH: git@hostname:owner/repo.git
    - GIT: git://hostname/owner/repo.git

    Args:
        url: Git remote URL

    Returns:
        RemoteDetail with parsed components

    Raises:
        ConfigurationError: If URL format is invalid
    """
    url = url.strip()

    # HTTPS pattern
    https_match = re.match(r'^https://(?:[^@]+@)?([^/]+)/(.+?)(\.git)?$', url)
    if https_match:
        hostname = https_match.group(1)
        repository = https_match.group(2)
        return RemoteDetail(
            protocol=GitProtocol.HTTPS,
            hostname=hostname,
            repository=repository
        )

    # SSH pattern
    ssh_match = re.match(r'^git@([^:]+):(.+?)(\.git)?$', url)
    if ssh_match:
        hostname = ssh_match.group(1)
        repository = ssh_match.group(2)
        return RemoteDetail(
            protocol=GitProtocol.SSH,
            hostname=hostname,
            repository=repository
        )

    # GIT pattern
    git_match = re.match(r'^git://([^/]+)/(.+?)(\.git)?$', url)
    if git_match:
        hostname = git_match.group(1)
        repository = git_match.group(2)
        return RemoteDetail(
            protocol=GitProtocol.GIT,
            hostname=hostname,
            repository=repository
        )

    raise ConfigurationError("remote-url", f"Unable to parse remote URL: {url}")


def parse_git_diff_output(output: str) -> List[Tuple[str, str]]:
    """
    Parse git diff --name-status output.

    Args:
        output: Output from git diff --name-status

    Returns:
        List of (status, path) tuples
    """
    files = []
    for line in output.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t", maxsplit=1)
        if len(parts) == 2:
            status = parts[0]
            path = parts[1]
            files.append((status, path))
    return files


def strip_org_prefix_from_teams(teams: List[str]) -> List[str]:
    """
    Strip organization prefix from team names.
    Converts "org/team-name" to "team-name".

    Args:
        teams: List of team identifiers

    Returns:
        List of team names without org prefix
    """
    stripped = []
    for team in teams:
        if '/' in team:
            # Take everything after the last slash
            stripped.append(team.split('/')[-1])
        else:
            stripped.append(team)
    return stripped


def get_repo_path(relative_path: Optional[str] = None) -> str:
    """
    Get absolute repository path.
    Resolves relative to GITHUB_WORKSPACE if available.

    Args:
        relative_path: Path relative to workspace

    Returns:
        Absolute path to repository
    """
    workspace = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

    if relative_path:
        return str(Path(workspace) / relative_path)

    return workspace


def file_exists(path: str) -> bool:
    """
    Check if file exists.

    Args:
        path: File path to check

    Returns:
        True if file exists, False otherwise
    """
    return Path(path).is_file()


def read_file(path: str) -> str:
    """
    Read file contents.

    Args:
        path: File path to read

    Returns:
        File contents as string

    Raises:
        ConfigurationError: If file doesn't exist or can't be read
    """
    try:
        return Path(path).read_text(encoding='utf-8')
    except FileNotFoundError:
        raise ConfigurationError("file", f"File not found: {path}")
    except Exception as e:
        raise ConfigurationError("file", f"Error reading file {path}: {str(e)}")


def get_error_message(error: Exception) -> str:
    """
    Extract error message from exception.

    Args:
        error: Exception object

    Returns:
        Error message as string
    """
    return str(error) if error else "Unknown error"


def is_self_hosted() -> bool:
    """
    Detect if running on self-hosted runner.

    Returns:
        True if self-hosted, False otherwise
    """
    # Check environment variables that indicate self-hosted runner
    runner_env = os.environ.get("RUNNER_ENVIRONMENT", "")
    agent_self_hosted = os.environ.get("AGENT_ISSELFHOSTED", "")

    return runner_env == "self-hosted" or agent_self_hosted == "true"


def seconds_since_epoch() -> int:
    """
    Get seconds since Unix epoch.

    Returns:
        Integer seconds since epoch (10 digits)
    """
    return int(datetime.now().timestamp())


def random_string(length: int = 7) -> str:
    """
    Generate random string.

    Args:
        length: Length of string to generate

    Returns:
        Random string of specified length
    """
    return str(uuid.uuid4()).replace('-', '')[:length]
