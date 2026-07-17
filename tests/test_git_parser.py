"""
Tests for gitmind/parsers/git_parser.py

Week 1: write these tests AS you implement the parser.
Test-driven development helps here because you can validate
each small piece before wiring everything together.

Run with:  pytest tests/test_git_parser.py -v
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from gitmind.parsers.git_parser import parse_commits, _extract_files_changed


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def this_repo() -> Path:
    """Use the gitmind repo itself as a test fixture — it IS a git repo."""
    return Path(__file__).parent.parent


# ── Tests for parse_commits ────────────────────────────────────────────────────

@pytest.mark.skip(reason="TODO Week 1: implement parse_commits first")
def test_parse_commits_returns_commits(this_repo):
    """parse_commits should yield at least one Commit for a non-empty repo."""
    commits = list(parse_commits(this_repo))
    assert len(commits) > 0


@pytest.mark.skip(reason="TODO Week 1: implement parse_commits first")
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


@pytest.mark.skip(reason="TODO Week 1: implement parse_commits first")
def test_merge_commits_are_skipped(this_repo):
    """Merge commits should be excluded — they add noise without rationale."""
    commits = list(parse_commits(this_repo))
    for commit in commits:
        # A merge commit message typically starts with "Merge"
        # This is a soft check — a better one requires checking parent count
        assert not commit.message.startswith("Merge branch"), \
            f"Merge commit should be skipped: {commit.short_hash}"


@pytest.mark.skip(reason="TODO Week 1: implement parse_commits first")
def test_commits_are_sorted_newest_first(this_repo):
    """Commits should be yielded newest-first (standard git log order)."""
    commits = list(parse_commits(this_repo))
    timestamps = [c.timestamp for c in commits]
    assert timestamps == sorted(timestamps, reverse=True)


@pytest.mark.skip(reason="TODO Week 1: implement parse_commits first")
def test_invalid_repo_raises_value_error():
    """parse_commits should raise ValueError for a non-git directory."""
    with pytest.raises(ValueError, match="not a git repository"):
        list(parse_commits(Path("/tmp")))


# ── Tests for _extract_files_changed ──────────────────────────────────────────

@pytest.mark.skip(reason="TODO Week 1: implement _extract_files_changed first")
def test_extract_files_changed_basic():
    """Should return all modified file paths from a diff object."""
    # TODO: construct a mock GitPython diff object and test against it
    pass


@pytest.mark.skip(reason="TODO Week 1: implement _extract_files_changed first")
def test_extract_files_changed_handles_renames():
    """For renamed files, should return the new (b_path) name."""
    pass
