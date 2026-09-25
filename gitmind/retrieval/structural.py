"""
Structural Index — Week 2.

BM25 index over the codebase AST: files → functions → callsites → imports.
Answers "where" queries like "where does the retry logic live?"

Uses tree-sitter (via ast_extractor) to extract function/class definitions
and rank-bm25 (BM25Plus) for retrieval.
"""

from __future__ import annotations

import logging
import pickle
import re
from pathlib import Path

from gitmind.config import settings
from gitmind.parsers.ast_extractor import extract_symbols

logger = logging.getLogger(__name__)

# File extensions to index
_INDEXABLE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs",
    ".java", ".cpp", ".c", ".rb", ".swift", ".kt",
}


class StructuralIndex:
    """BM25 index over the codebase structure."""

    def __init__(self):
        self._documents: list[dict] = []  # [{path, name, type, text, start_line, end_line}]
        self._corpus: list[list[str]] = []
        self._bm25 = None

    def build(self, repo_path: Path) -> None:
        """
        Walk the repo and index all code files.

        Extracts function names, class names, and docstrings from source files.
        """
        self._documents = []
        self._corpus = []

        for file_path in _walk_code_files(repo_path):
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                rel_path = str(file_path.relative_to(repo_path))

                # Extract structural elements from the file
                elements = _extract_structural_elements(content, rel_path, file_path.suffix)

                for elem in elements:
                    self._documents.append(elem)
                    # Tokenize for BM25: index symbol name, full signature, docstring, and path
                    text_blob = (
                        f"{elem['name']} {elem.get('signature', '')} "
                        f"{elem.get('docstring', '')} {elem['text']} {elem['path']}"
                    )
                    tokens = _tokenize(text_blob)
                    self._corpus.append(tokens)

            except Exception as e:
                logger.debug("Failed to index %s: %s", file_path, e)
                continue

        if self._corpus:
            from rank_bm25 import BM25Plus
            self._bm25 = BM25Plus(self._corpus)
            logger.info("Built structural index with %d entries", len(self._documents))
        else:
            logger.warning("No code files found to index")

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Search the structural index for code elements matching the query.

        Returns a list of dicts with keys: path, name, type, text, score.
        """
        if not self._bm25 or not self._documents:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)

        # Pair documents with scores and sort by score DESC
        scored = [(self._documents[i], scores[i]) for i in range(len(self._documents))]
        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for doc, score in scored[:top_k]:
            if score > 0:
                results.append({**doc, "score": float(score)})

        return results

    def save(self) -> None:
        """Serialize the index to disk."""
        settings.ensure_data_dir()
        data = {
            "documents": self._documents,
            "corpus": self._corpus,
        }
        with open(settings.bm25_index_path, "wb") as f:
            pickle.dump(data, f)
        logger.info("Saved structural index to %s", settings.bm25_index_path)

    def load(self) -> None:
        """Load the index from disk."""
        if not settings.bm25_index_path.exists():
            logger.warning("No structural index found at %s", settings.bm25_index_path)
            return

        with open(settings.bm25_index_path, "rb") as f:
            data = pickle.load(f)

        self._documents = data["documents"]
        self._corpus = data["corpus"]

        if self._corpus:
            from rank_bm25 import BM25Plus
            self._bm25 = BM25Plus(self._corpus)
            logger.info("Loaded structural index with %d entries", len(self._documents))


def _walk_code_files(repo_path: Path) -> list[Path]:
    """Walk the repo and return all indexable code files."""
    ignored_dirs = {
        "node_modules", "__pycache__", "venv", ".venv",
        "dist", "build", "vscode-gitmind"
    }
    files = []
    for f in repo_path.rglob("*"):
        if f.is_file() and f.suffix in _INDEXABLE_EXTENSIONS:
            # Skip hidden dirs, node_modules, venvs, etc.
            parts = f.relative_to(repo_path).parts
            skip = any(p.startswith(".") or p in ignored_dirs for p in parts)
            if not skip:
                files.append(f)
    return files


def _extract_structural_elements(content: str, rel_path: str, suffix: str) -> list[dict]:
    """
    Extract structural elements (files, functions, classes) from source code
    using Tree-sitter symbol extraction.
    """
    elements: list[dict] = []

    # File overview document
    first_lines = "\n".join(content.splitlines()[:15])
    elements.append({
        "path": rel_path,
        "name": rel_path,
        "type": "file",
        "text": first_lines,
        "start_line": 1,
        "end_line": len(content.splitlines()),
    })

    # AST symbol extraction
    symbols = extract_symbols(content, suffix)
    lines = content.splitlines()

    for sym in symbols:
        # Extract snippet preview
        start_idx = max(0, sym.start_line - 1)
        end_idx = min(len(lines), sym.end_line)
        preview_lines = lines[start_idx:min(start_idx + 10, end_idx)]
        preview = "\n".join(preview_lines)

        elements.append({
            "path": rel_path,
            "name": sym.name,
            "type": sym.symbol_type,
            "text": preview,
            "signature": sym.signature or "",
            "docstring": sym.docstring or "",
            "start_line": sym.start_line,
            "end_line": sym.end_line,
        })

    return elements


def _tokenize(text: str) -> list[str]:
    """
    Tokenize text into keywords for BM25 with camelCase and snake_case splitting.
    """
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    s = s.replace("_", " ").replace("-", " ")
    tokens = re.findall(r"\w+", s.lower())
    orig_words = [w.lower() for w in re.findall(r"\w+", text) if len(w) > 1]
    combined = [t for t in tokens if len(t) > 1] + orig_words
    return list(dict.fromkeys(combined))
