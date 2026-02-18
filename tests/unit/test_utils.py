"""
Unit tests for utility functions.

Tests parsing, formatting, and helper functions.
"""

import pytest
from create_pull_request.utils import (
    get_string_as_array,
    parse_display_name_email,
    parse_remote_url,
    get_remote_url,
    generate_branch_suffix,
    strip_org_prefix_from_teams,
)
from create_pull_request.models import GitProtocol
from create_pull_request.exceptions import ConfigurationError


class TestGetStringAsArray:
    """Tests for get_string_as_array function."""

    def test_comma_separated(self):
        """Test parsing comma-separated strings."""
        result = get_string_as_array("label1, label2, label3")
        assert result == ["label1", "label2", "label3"]

    def test_newline_separated(self):
        """Test parsing newline-separated strings."""
        result = get_string_as_array("label1\nlabel2\nlabel3")
        assert result == ["label1", "label2", "label3"]

    def test_mixed_separators(self):
        """Test parsing mixed separators."""
        result = get_string_as_array("label1, label2\nlabel3")
        assert result == ["label1", "label2", "label3"]

    def test_empty_string(self):
        """Test parsing empty string."""
        result = get_string_as_array("")
        assert result == []

    def test_whitespace_handling(self):
        """Test whitespace is trimmed."""
        result = get_string_as_array("  label1  ,  label2  ")
        assert result == ["label1", "label2"]


class TestParseDisplayNameEmail:
    """Tests for parse_display_name_email function."""

    def test_full_format(self):
        """Test parsing full name and email."""
        result = parse_display_name_email("John Doe <john@example.com>")
        assert result.name == "John Doe"
        assert result.email == "john@example.com"

    def test_with_extra_spaces(self):
        """Test parsing with extra spaces."""
        result = parse_display_name_email("  John Doe  <  john@example.com  >  ")
        assert result.name == "John Doe"
        assert result.email == "john@example.com"

    def test_name_only(self):
        """Test parsing name without email."""
        result = parse_display_name_email("John Doe")
        assert result.name == "John Doe"
        assert result.email == ""

    def test_empty_string_raises_error(self):
        """Test empty string raises ConfigurationError."""
        with pytest.raises(ConfigurationError):
            parse_display_name_email("")


class TestParseRemoteUrl:
    """Tests for parse_remote_url function."""

    def test_https_url(self):
        """Test parsing HTTPS URL."""
        result = parse_remote_url("https://github.com/owner/repo.git")
        assert result.protocol == GitProtocol.HTTPS
        assert result.hostname == "github.com"
        assert result.repository == "owner/repo"

    def test_https_url_without_git_extension(self):
        """Test parsing HTTPS URL without .git."""
        result = parse_remote_url("https://github.com/owner/repo")
        assert result.protocol == GitProtocol.HTTPS
        assert result.hostname == "github.com"
        assert result.repository == "owner/repo"

    def test_https_url_with_user(self):
        """Test parsing HTTPS URL with user."""
        result = parse_remote_url("https://user@github.com/owner/repo.git")
        assert result.protocol == GitProtocol.HTTPS
        assert result.hostname == "github.com"
        assert result.repository == "owner/repo"

    def test_ssh_url(self):
        """Test parsing SSH URL."""
        result = parse_remote_url("git@github.com:owner/repo.git")
        assert result.protocol == GitProtocol.SSH
        assert result.hostname == "github.com"
        assert result.repository == "owner/repo"

    def test_git_protocol_url(self):
        """Test parsing git:// URL."""
        result = parse_remote_url("git://github.com/owner/repo.git")
        assert result.protocol == GitProtocol.GIT
        assert result.hostname == "github.com"
        assert result.repository == "owner/repo"

    def test_invalid_url_raises_error(self):
        """Test invalid URL raises ConfigurationError."""
        with pytest.raises(ConfigurationError):
            parse_remote_url("invalid://url")


class TestGetRemoteUrl:
    """Tests for get_remote_url function."""

    def test_https_url(self):
        """Test building HTTPS URL."""
        result = get_remote_url(GitProtocol.HTTPS, "github.com", "owner/repo")
        assert result == "https://github.com/owner/repo.git"

    def test_ssh_url(self):
        """Test building SSH URL."""
        result = get_remote_url(GitProtocol.SSH, "github.com", "owner/repo")
        assert result == "git@github.com:owner/repo.git"

    def test_git_url(self):
        """Test building git:// URL."""
        result = get_remote_url(GitProtocol.GIT, "github.com", "owner/repo")
        assert result == "git://github.com/owner/repo.git"


class TestGenerateBranchSuffix:
    """Tests for generate_branch_suffix function."""

    def test_none_suffix(self):
        """Test none suffix returns empty string."""
        result = generate_branch_suffix("none")
        assert result == ""

    def test_timestamp_suffix(self):
        """Test timestamp suffix returns numeric string."""
        result = generate_branch_suffix("timestamp")
        assert result.isdigit()
        assert len(result) == 10  # Unix timestamp is 10 digits

    def test_random_suffix(self):
        """Test random suffix returns 7-character string."""
        result = generate_branch_suffix("random")
        assert len(result) == 7

    def test_invalid_suffix_raises_error(self):
        """Test invalid suffix type raises ConfigurationError."""
        with pytest.raises(ConfigurationError):
            generate_branch_suffix("invalid")


class TestStripOrgPrefixFromTeams:
    """Tests for strip_org_prefix_from_teams function."""

    def test_strip_prefix(self):
        """Test stripping org prefix from teams."""
        result = strip_org_prefix_from_teams(["org/team1", "org/team2"])
        assert result == ["team1", "team2"]

    def test_no_prefix(self):
        """Test teams without prefix remain unchanged."""
        result = strip_org_prefix_from_teams(["team1", "team2"])
        assert result == ["team1", "team2"]

    def test_mixed(self):
        """Test mixed teams with and without prefix."""
        result = strip_org_prefix_from_teams(["org/team1", "team2", "other-org/team3"])
        assert result == ["team1", "team2", "team3"]
