"""
Git Parser — Week 1 core task.

Reads a git repository's commit history using `git log --follow -p`
and produces a stream of Commit objects.

Public API:
    parse_commits(repo_path)  →  Iterator[Commit]

Implementation notes:
  - Use GitPython (git.Repo) to walk commits — cleaner than subprocess
  - The diff for each commit comes from commit.diff(commit.parents[0])
  - files_changed: list of all modified file paths in that commit
  - functions_touched: leave as [] for now — populated in Week 2 by tree-sitter
  - Skip merge commits (len(commit.parents) > 1) — they add noise
  - Skip commits older than GITMIND_MAX_HISTORY_DAYS if set

Week 1 TODO list (in order):
  [ ] Implement parse_commits() using GitPython
  [ ] Implement _extract_files_changed() from a GitPython diff object
  [ ] Implement _build_commit() to assemble the Commit model
  [ ] Handle the root commit edge case (no parents → use empty tree)
  [ ] Add a progress bar using rich.progress for large repos
  [ ] Write tests in tests/test_git_parser.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from gitmind.models import Commit


def parse_commits(repo_path: Path) -> Iterator[Commit]:
    """
    Walk the git history of repo_path and yield Commit objects.

    Args:
        repo_path: Path to the root of the git repository.

    Yields:
        Commit objects, from newest to oldest.

    Raises:
        ValueError: If repo_path is not a valid git repository.

    Example:
        for commit in parse_commits(Path("/my/project")):
            print(commit.short_hash, commit.message)

    TODO (Week 1): implement this.
    """
    raise NotImplementedError


def _extract_files_changed(diff_items: list) -> list[str]:
    """
    Extract the list of modified file paths from a GitPython diff.

    A diff item has .a_path (old path) and .b_path (new path).
    For renames, prefer b_path (the new name).

    TODO (Week 1): implement this.
    """
    raise NotImplementedError


def _build_commit(git_commit, diff_text: str, files_changed: list[str]) -> Commit:
    """
    Assemble a Commit model from a GitPython commit object.

    Args:
        git_commit: A gitpython.Commit object.
        diff_text:  The unified diff string for this commit.
        files_changed: List of modified file paths.

    TODO (Week 1): implement this.
    """
    raise NotImplementedError
