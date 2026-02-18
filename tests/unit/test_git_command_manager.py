"""
Unit tests for GitCommandManager.

Tests git command execution with mocked subprocess calls.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from create_pull_request.git_command_manager import GitCommandManager
from create_pull_request.exceptions import GitCommandError


class TestGitCommandManager:
    """Tests for GitCommandManager class."""

    @pytest.fixture
    def git_manager(self, tmp_path):
        """Create GitCommandManager instance."""
        return GitCommandManager(str(tmp_path))

    def test_initialization(self, tmp_path):
        """Test GitCommandManager initialization."""
        git = GitCommandManager(str(tmp_path))
        assert git.working_dir == tmp_path.resolve()

    @patch('subprocess.run')
    def test_exec_success(self, mock_run, git_manager):
        """Test successful git command execution."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="output",
            stderr=""
        )

        exit_code, stdout, stderr = git_manager.exec(["status"])

        assert exit_code == 0
        assert stdout == "output"
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_exec_failure(self, mock_run, git_manager):
        """Test failed git command execution."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="error message"
        )

        with pytest.raises(GitCommandError) as exc_info:
            git_manager.exec(["invalid-command"])

        assert exc_info.value.exit_code == 1
        assert "error message" in str(exc_info.value)

    @patch('subprocess.run')
    def test_exec_allow_all_exit_codes(self, mock_run, git_manager):
        """Test exec with allow_all_exit_codes."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="error"
        )

        exit_code, stdout, stderr = git_manager.exec(
            ["status"],
            allow_all_exit_codes=True
        )

        assert exit_code == 1
        assert stderr == "error"

    @patch('subprocess.run')
    def test_rev_parse(self, mock_run, git_manager):
        """Test rev_parse command."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123def456\n",
            stderr=""
        )

        sha = git_manager.rev_parse("HEAD")

        assert sha == "abc123def456"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "rev-parse" in args
        assert "HEAD" in args

    @patch('subprocess.run')
    def test_rev_parse_short(self, mock_run, git_manager):
        """Test rev_parse with short SHA."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123d\n",
            stderr=""
        )

        sha = git_manager.rev_parse("HEAD", short=True)

        assert sha == "abc123d"
        args = mock_run.call_args[0][0]
        assert "--short" in args

    @patch('subprocess.run')
    def test_branch_exists_remote_true(self, mock_run, git_manager):
        """Test branch_exists_remote when branch exists."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123  refs/heads/main\n",
            stderr=""
        )

        result = git_manager.branch_exists_remote("main")

        assert result is True

    @patch('subprocess.run')
    def test_branch_exists_remote_false(self, mock_run, git_manager):
        """Test branch_exists_remote when branch doesn't exist."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )

        result = git_manager.branch_exists_remote("nonexistent")

        assert result is False

    @patch('subprocess.run')
    def test_is_dirty_true(self, mock_run, git_manager):
        """Test is_dirty when working directory has changes."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=" M file.txt\n",
            stderr=""
        )

        result = git_manager.is_dirty()

        assert result is True

    @patch('subprocess.run')
    def test_is_dirty_false(self, mock_run, git_manager):
        """Test is_dirty when working directory is clean."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )

        result = git_manager.is_dirty()

        assert result is False

    @patch('subprocess.run')
    def test_has_diff_true(self, mock_run, git_manager):
        """Test has_diff when diff exists."""
        mock_run.return_value = Mock(
            returncode=1,  # git diff --quiet returns 1 when diff exists
            stdout="",
            stderr=""
        )

        result = git_manager.has_diff("main", "feature")

        assert result is True

    @patch('subprocess.run')
    def test_has_diff_false(self, mock_run, git_manager):
        """Test has_diff when no diff exists."""
        mock_run.return_value = Mock(
            returncode=0,  # git diff --quiet returns 0 when no diff
            stdout="",
            stderr=""
        )

        result = git_manager.has_diff("main", "feature")

        assert result is False


class TestGitCommandManagerIntegration:
    """Integration tests with real git repository."""

    def test_real_git_operations(self, temp_repo):
        """Test real git operations on temporary repository."""
        git = GitCommandManager(str(temp_repo))

        # Test rev-parse
        sha = git.rev_parse("HEAD")
        assert len(sha) == 40  # Full SHA length

        # Test short SHA
        short_sha = git.rev_parse("HEAD", short=True)
        assert len(short_sha) == 7

        # Test current branch
        branch = git.get_current_branch()
        assert branch in ["main", "master"]  # Depends on git version

        # Test is_dirty on clean repo
        assert git.is_dirty() is False

        # Create a file and test is_dirty
        (temp_repo / "new_file.txt").write_text("content")
        assert git.is_dirty(include_untracked=True) is True
