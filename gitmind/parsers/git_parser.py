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
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import git

from gitmind.models import Commit

logger = logging.getLogger(__name__)

# GitPython uses this special SHA to represent the empty tree (for root commits)
_EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf899d15363da9030"


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
    """
    try:
        repo = git.Repo(repo_path, search_parent_directories=True)
    except git.InvalidGitRepositoryError:
        raise ValueError(f"{repo_path} is not a git repository")

    for git_commit in repo.iter_commits():
        # Skip merge commits — they add noise without rationale
        if len(git_commit.parents) > 1:
            logger.debug("Skipping merge commit %s", git_commit.hexsha[:7])
            continue

        try:
            # Get the diff against the parent (or empty tree for root commit)
            if git_commit.parents:
                parent = git_commit.parents[0]
                diff_items = parent.diff(git_commit, create_patch=True)
            else:
                # Root commit: diff against the empty tree
                # Use git hash-object to ensure the empty tree exists
                try:
                    empty_tree = git_commit.repo.git.hash_object(
                        "-t", "tree", "--stdin", istream=b""
                    )
                    diff_items = git_commit.diff(
                        empty_tree, create_patch=True, R=True
                    )
                except Exception:
                    # Fallback: just list the tree entries as files
                    diff_items = []

            files_changed = _extract_files_changed(diff_items)

            # Build the unified diff text
            diff_text = _build_diff_text(diff_items)

            yield _build_commit(git_commit, diff_text, files_changed)

        except Exception as e:
            logger.warning(
                "Failed to parse commit %s: %s", git_commit.hexsha[:7], e
            )
            continue


def _extract_files_changed(diff_items: list) -> list[str]:
    """
    Extract the list of modified file paths from a GitPython diff.

    A diff item has .a_path (old path) and .b_path (new path).
    For renames, prefer b_path (the new name).
    """
    paths: list[str] = []
    for d in diff_items:
        # Prefer b_path (destination / new name), fall back to a_path
        path = d.b_path or d.a_path
        if path and path not in paths:
            paths.append(path)
    return paths


def _build_diff_text(diff_items: list) -> str:
    """
    Build a unified diff string from GitPython diff items.
    """
    parts: list[str] = []
    for d in diff_items:
        try:
            diff_bytes = d.diff
            if diff_bytes:
                if isinstance(diff_bytes, bytes):
                    parts.append(diff_bytes.decode("utf-8", errors="replace"))
                else:
                    parts.append(str(diff_bytes))
        except Exception:
            continue
    return "\n".join(parts)


def _build_commit(git_commit, diff_text: str, files_changed: list[str]) -> Commit:
    """
    Assemble a Commit model from a GitPython commit object.

    Args:
        git_commit: A gitpython.Commit object.
        diff_text:  The unified diff string for this commit.
        files_changed: List of modified file paths.
    """
    return Commit(
        hash=git_commit.hexsha,
        short_hash=git_commit.hexsha[:7],
        message=git_commit.message.strip(),
        author=str(git_commit.author),
        timestamp=datetime.fromtimestamp(
            git_commit.committed_date, tz=timezone.utc
        ),
        diff=diff_text,
        files_changed=files_changed,
        functions_touched=[],  # populated in Week 2 by tree-sitter
    )
