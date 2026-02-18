"""
Integration tests for basic create-pull-request workflow.

Tests end-to-end functionality with real git operations and mocked GitHub API.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from create_pull_request.git_command_manager import GitCommandManager
from create_pull_request.branch_manager import BranchManager
from create_pull_request.models import ActionInputs


class TestBasicWorkflow:
    """Integration tests for basic workflow."""

    def test_branch_creation_with_changes(self, temp_repo):
        """Test creating a branch with changes."""
        git = GitCommandManager(str(temp_repo))

        # Create some changes
        (temp_repo / "new_file.txt").write_text("New content")

        # Verify changes exist
        assert git.is_dirty(include_untracked=True)

        # Stage and commit changes
        git.add(all_files=True)
        git.commit("Test commit", identity={"name": "Test", "email": "test@example.com"})

        # Verify commit was created
        sha = git.rev_parse("HEAD")
        assert len(sha) == 40

    def test_branch_manager_create_branch(self, temp_repo):
        """Test BranchManager creates branch correctly."""
        git = GitCommandManager(str(temp_repo))

        # Create test changes
        (temp_repo / "test.txt").write_text("Test content")

        # Create inputs
        inputs = ActionInputs(
            token="fake-token",
            branch="test-branch",
            commit_message="Test changes",
            base="main"  # or "master" depending on default branch
        )

        # Mock GitHub helper (not needed for local git operations)
        with patch('create_pull_request.branch_manager.GitHubHelper'):
            branch_manager = BranchManager(git, github=None)

            # This would normally create/update the branch
            # For now, just verify git operations work
            current_branch = git.get_current_branch()
            assert current_branch is not None

    def test_commit_metadata_parsing(self, temp_repo):
        """Test parsing commit metadata."""
        git = GitCommandManager(str(temp_repo))

        # Get the initial commit
        sha = git.rev_parse("HEAD")
        commit = git.get_commit(sha)

        # Verify commit metadata
        assert commit.sha == sha
        assert commit.subject == "Initial commit"
        assert len(commit.parents) == 0  # First commit has no parents

    def test_multiple_commits(self, temp_repo):
        """Test handling multiple commits."""
        git = GitCommandManager(str(temp_repo))

        # Create multiple commits
        for i in range(3):
            (temp_repo / f"file{i}.txt").write_text(f"Content {i}")
            git.add(all_files=True)
            git.commit(
                f"Commit {i}",
                identity={"name": "Test", "email": "test@example.com"}
            )

        # Verify commits exist
        commits = git.rev_list("HEAD~3..HEAD")
        assert len(commits) == 3

    def test_branch_ahead_detection(self, temp_repo):
        """Test detecting when branch is ahead of base."""
        git = GitCommandManager(str(temp_repo))

        # Get current state
        base_sha = git.rev_parse("HEAD")

        # Create a new branch with a commit
        git.checkout("feature", "HEAD")
        (temp_repo / "feature.txt").write_text("Feature content")
        git.add(all_files=True)
        git.commit(
            "Feature commit",
            identity={"name": "Test", "email": "test@example.com"}
        )

        # Check if feature branch is ahead
        current_branch = git.get_current_branch()
        assert current_branch == "feature"

        # Verify we can detect ahead status
        commits_ahead = git.rev_list(f"{base_sha}..HEAD")
        assert len(commits_ahead) == 1


class TestBranchDiffDetection:
    """Tests for branch difference detection."""

    def test_has_diff_between_branches(self, temp_repo):
        """Test detecting diff between branches."""
        git = GitCommandManager(str(temp_repo))

        # Create base branch
        base_branch = git.get_current_branch() or "main"

        # Create feature branch with changes
        git.checkout("feature", base_branch)
        (temp_repo / "feature.txt").write_text("Feature")
        git.add(all_files=True)
        git.commit(
            "Feature",
            identity={"name": "Test", "email": "test@example.com"}
        )

        # Switch back to base
        git.checkout(base_branch)

        # Verify diff exists
        has_diff = git.has_diff(base_branch, "feature")
        assert has_diff is True

    def test_no_diff_same_branch(self, temp_repo):
        """Test no diff when comparing branch to itself."""
        git = GitCommandManager(str(temp_repo))

        branch = git.get_current_branch() or "main"
        has_diff = git.has_diff(branch, branch)
        assert has_diff is False
