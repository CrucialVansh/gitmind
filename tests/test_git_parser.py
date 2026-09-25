"""
Tests for gitmind/parsers/git_parser.py

Run with:  pytest tests/test_git_parser.py -v
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gitmind.parsers.git_parser import parse_commits, _extract_files_changed, _build_commit


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def this_repo() -> Path:
    """Use the gitmind repo itself as a test fixture — it IS a git repo."""
    return Path(__file__).parent.parent


# ── Tests for parse_commits ────────────────────────────────────────────────────

def test_parse_commits_returns_commits(this_repo):
    """parse_commits should yield at least one Commit for a non-empty repo."""
    commits = list(parse_commits(this_repo))
    assert len(commits) > 0


def test_commit_has_required_fields(this_repo):
    """Every Commit should have all required fields populated."""
    commits = list(parse_commits(this_repo))
    first = commits[0]

    assert first.hash and len(first.hash) == 40
    assert first.short_hash and len(first.short_hash) == 7
    assert first.message
    assert first.author
    assert isinstance(first.timestamp, datetime)
    assert isinstance(first.files_changed, list)


def test_merge_commits_are_skipped(this_repo):
    """Merge commits should be excluded — they add noise without rationale."""
    commits = list(parse_commits(this_repo))
    for commit in commits:
        # A merge commit message typically starts with "Merge"
        # This is a soft check — a better one requires checking parent count
        assert not commit.message.startswith("Merge branch"), \
            f"Merge commit should be skipped: {commit.short_hash}"


def test_commits_are_sorted_newest_first(this_repo):
    """Commits should be yielded newest-first (standard git log order)."""
    commits = list(parse_commits(this_repo))
    timestamps = [c.timestamp for c in commits]
    assert timestamps == sorted(timestamps, reverse=True)


def test_invalid_repo_raises_value_error():
    """parse_commits should raise ValueError for a non-git directory."""
    with pytest.raises(ValueError, match="not a git repository"):
        list(parse_commits(Path("/tmp")))


# ── Tests for _extract_files_changed ──────────────────────────────────────────

def test_extract_files_changed_basic():
    """Should return all modified file paths from a diff object."""
    mock_diff_1 = MagicMock()
    mock_diff_1.a_path = "old_name.py"
    mock_diff_1.b_path = "src/api.py"

    mock_diff_2 = MagicMock()
    mock_diff_2.a_path = "tests/test_api.py"
    mock_diff_2.b_path = "tests/test_api.py"

    result = _extract_files_changed([mock_diff_1, mock_diff_2])
    assert "src/api.py" in result
    assert "tests/test_api.py" in result
    assert len(result) == 2


def test_extract_files_changed_handles_renames():
    """For renamed files, should return the new (b_path) name."""
    mock_diff = MagicMock()
    mock_diff.a_path = "old_name.py"
    mock_diff.b_path = "new_name.py"

    result = _extract_files_changed([mock_diff])
    assert result == ["new_name.py"]


def test_extract_files_changed_deduplicates():
    """Should not return duplicate paths."""
    mock_diff_1 = MagicMock()
    mock_diff_1.a_path = "src/api.py"
    mock_diff_1.b_path = "src/api.py"

    mock_diff_2 = MagicMock()
    mock_diff_2.a_path = "src/api.py"
    mock_diff_2.b_path = "src/api.py"

    result = _extract_files_changed([mock_diff_1, mock_diff_2])
    assert result == ["src/api.py"]


def test_extract_files_changed_falls_back_to_a_path():
    """If b_path is None (deletion), should use a_path."""
    mock_diff = MagicMock()
    mock_diff.a_path = "deleted_file.py"
    mock_diff.b_path = None

    result = _extract_files_changed([mock_diff])
    assert result == ["deleted_file.py"]


# ── Tests for _build_commit ──────────────────────────────────────────────────

def test_build_commit():
    """Should correctly map GitPython commit fields to the Pydantic model."""
    mock_commit = MagicMock()
    mock_commit.hexsha = "a" * 40
    mock_commit.message = "test commit message\n"
    mock_commit.author = "Test Author"
    mock_commit.committed_date = 1700000000  # some Unix timestamp

    result = _build_commit(mock_commit, "diff text", ["src/api.py"])

    assert result.hash == "a" * 40
    assert result.short_hash == "aaaaaaa"
    assert result.message == "test commit message"
    assert result.author == "Test Author"
    assert result.diff == "diff text"
    assert result.files_changed == ["src/api.py"]
    assert result.functions_touched == []
