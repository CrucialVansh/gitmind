"""
Git Parser — Week 1 + Week 2 core task.

Reads a git repository's commit history using `git log --follow -p`
and produces a stream of Commit objects with functions_touched extracted via AST.

Public API:
    parse_commits(repo_path)  →  Iterator[Commit]
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import git

from gitmind.models import Commit
from gitmind.parsers.ast_extractor import extract_symbols, find_touched_functions

logger = logging.getLogger(__name__)


def parse_commits(repo_path: Path) -> Iterator[Commit]:
    """
    Walk the git history of repo_path and yield Commit objects.

    Args:
        repo_path: Path to the root of the git repository.

    Yields:
        Commit objects, from newest to oldest.

    Raises:
        ValueError: If repo_path is not a valid git repository.
    """
    try:
        repo = git.Repo(repo_path, search_parent_directories=True)
    except git.InvalidGitRepositoryError as exc:
        raise ValueError(f"{repo_path} is not a git repository") from exc

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
                try:
                    empty_tree = git_commit.repo.git.hash_object(
                        "-t", "tree", "--stdin", istream=b""
                    )
                    diff_items = git_commit.diff(
                        empty_tree, create_patch=True, R=True
                    )
                except Exception:
                    diff_items = []

            files_changed = _extract_files_changed(diff_items)
            diff_text = _build_diff_text(diff_items)
            functions_touched = _extract_functions_touched(git_commit, diff_items)

            yield _build_commit(git_commit, diff_text, files_changed, functions_touched)

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
        path = d.b_path or d.a_path
        if path and path not in paths:
            paths.append(path)
    return paths


def _build_diff_text(diff_items: list) -> str:
    """Build a unified diff string from GitPython diff items."""
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


def _extract_functions_touched(git_commit, diff_items: list) -> list[str]:
    """
    Analyze the diff hunks and file AST to find all functions and classes
    modified in this commit.
    """
    functions_touched: list[str] = []

    for d in diff_items:
        path = d.b_path or d.a_path
        if not path:
            continue

        suffix = Path(path).suffix.lower()
        if suffix not in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"):
            continue

        if isinstance(d.diff, bytes):
            diff_content = d.diff.decode("utf-8", errors="replace")
        else:
            diff_content = str(d.diff or "")

        # Extract modified line ranges in the destination file
        ranges: list[tuple[int, int]] = []
        for m in re.finditer(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff_content):
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            end = start + max(1, count) - 1
            ranges.append((start, end))

        if not ranges:
            continue

        # Get file content from the commit tree (or fallback to parent for deleted)
        content_bytes = None
        try:
            blob = git_commit.tree[path]
            content_bytes = blob.data_stream.read()
        except Exception:
            if git_commit.parents:
                try:
                    blob = git_commit.parents[0].tree[path]
                    content_bytes = blob.data_stream.read()
                except Exception:
                    pass

        if content_bytes:
            symbols = extract_symbols(content_bytes, suffix)
            touched = find_touched_functions(symbols, ranges)
            for fn in touched:
                if fn not in functions_touched:
                    functions_touched.append(fn)

    return functions_touched


def _build_commit(
    git_commit,
    diff_text: str,
    files_changed: list[str],
    functions_touched: list[str] | None = None,
) -> Commit:
    """Assemble a Commit model from a GitPython commit object."""
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
        functions_touched=functions_touched or [],
    )
