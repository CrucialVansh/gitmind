"""
Structural Index — Week 2.

BM25 index over the codebase AST: files → functions → callsites → imports.
Answers "where" queries like "where does the retry logic live?"

TODO (Week 2):
  [ ] Parse repo with tree-sitter (Python + TypeScript + Go)
  [ ] Build BM25 index over structured node text
  [ ] Implement search() returning ranked file/function paths
  [ ] Serialize/deserialize index to settings.bm25_index_path
"""

from __future__ import annotations
from pathlib import Path


class StructuralIndex:
    """BM25 index over the codebase AST. Implemented in Week 2."""

    def build(self, repo_path: Path) -> None:
        raise NotImplementedError("Week 2")

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        raise NotImplementedError("Week 2")

    def save(self) -> None:
        raise NotImplementedError("Week 2")

    def load(self) -> None:
        raise NotImplementedError("Week 2")
