"""
Pytest configuration and fixtures for create-pull-request tests.

Provides common fixtures for testing git operations and GitHub API interactions.
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import Generator
import pytest


@pytest.fixture
def temp_repo() -> Generator[Path, None, None]:
    """
    Create a temporary git repository for testing.

    Yields:
        Path to temporary repository
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

        # Create initial commit
        (repo_path / "README.md").write_text("# Test Repo\n")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

        yield repo_path


@pytest.fixture
def mock_github_env(monkeypatch):
    """
    Mock GitHub Actions environment variables.
    """
    monkeypatch.setenv("GITHUB_REPOSITORY", "test-owner/test-repo")
    monkeypatch.setenv("GITHUB_WORKSPACE", "/tmp/workspace")
    monkeypatch.setenv("GITHUB_ACTOR", "test-actor")
    monkeypatch.setenv("INPUT_TOKEN", "fake-token")


def create_test_file(repo_path: Path, filename: str, content: str = "test content") -> None:
    """
    Create a test file in the repository.

    Args:
        repo_path: Repository path
        filename: File name
        content: File content
    """
    (repo_path / filename).write_text(content)


def create_test_commit(repo_path: Path, message: str = "Test commit") -> str:
    """
    Create a test commit in the repository.

    Args:
        repo_path: Repository path
        message: Commit message

    Returns:
        Commit SHA
    """
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_path,
        check=True,
        capture_output=True
    )

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True
    )

    return result.stdout.strip()
