"""
Structural Index — Week 2.

BM25 index over the codebase AST: files → functions → callsites → imports.
Answers "where" queries like "where does the retry logic live?"

Uses tree-sitter to extract function/class definitions and rank-bm25 for retrieval.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

from gitmind.config import settings

logger = logging.getLogger(__name__)

# File extensions to index
_INDEXABLE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs",
    ".java", ".cpp", ".c", ".rb", ".swift", ".kt",
}


class StructuralIndex:
    """BM25 index over the codebase structure."""

    def __init__(self):
        self._documents: list[dict] = []  # [{path, name, type, text}]
        self._corpus: list[list[str]] = []
        self._bm25 = None

    def build(self, repo_path: Path) -> None:
        """
        Walk the repo and index all code files.

        Extracts function names, class names, and docstrings from source files.
        Falls back to line-based indexing if tree-sitter isn't available.
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
                    # Tokenize for BM25
                    tokens = _tokenize(f"{elem['name']} {elem['text']} {elem['path']}")
                    self._corpus.append(tokens)

            except Exception as e:
                logger.debug("Failed to index %s: %s", file_path, e)
                continue

        if self._corpus:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi(self._corpus)
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
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi(self._corpus)
            logger.info("Loaded structural index with %d entries", len(self._documents))


def _walk_code_files(repo_path: Path) -> list[Path]:
    """Walk the repo and return all indexable code files."""
    files = []
    for f in repo_path.rglob("*"):
        if f.is_file() and f.suffix in _INDEXABLE_EXTENSIONS:
            # Skip hidden dirs, node_modules, venvs, etc.
            parts = f.relative_to(repo_path).parts
            skip = any(
                p.startswith(".") or p in ("node_modules", "__pycache__", "venv", ".venv", "dist", "build")
                for p in parts
            )
            if not skip:
                files.append(f)
    return files


def _extract_structural_elements(content: str, rel_path: str, suffix: str) -> list[dict]:
    """
    Extract structural elements (functions, classes) from source code.

    Uses regex-based extraction as a portable fallback.
    """
    elements = []

    # Always add the file itself as an element
    first_lines = "\n".join(content.split("\n")[:10])
    elements.append({
        "path": rel_path,
        "name": rel_path,
        "type": "file",
        "text": first_lines,
    })

    if suffix == ".py":
        elements.extend(_extract_python_elements(content, rel_path))
    elif suffix in (".ts", ".tsx", ".js", ".jsx"):
        elements.extend(_extract_js_ts_elements(content, rel_path))
    elif suffix == ".go":
        elements.extend(_extract_go_elements(content, rel_path))

    return elements


def _extract_python_elements(content: str, rel_path: str) -> list[dict]:
    """Extract Python functions and classes using regex."""
    import re
    elements = []

    # Functions
    for match in re.finditer(
        r'^([ \t]*)(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\).*?:[ \t]*\n([ \t]*(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'))?',
        content,
        re.MULTILINE,
    ):
        indent, name, params, docstring = match.groups()
        text = f"def {name}({params})"
        if docstring:
            text += f"\n{docstring.strip()}"
        elements.append({
            "path": rel_path,
            "name": name,
            "type": "function",
            "text": text,
        })

    # Classes
    for match in re.finditer(
        r'^class\s+(\w+)(?:\([^)]*\))?.*?:[ \t]*\n([ \t]*(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'))?',
        content,
        re.MULTILINE,
    ):
        name, docstring = match.groups()
        text = f"class {name}"
        if docstring:
            text += f"\n{docstring.strip()}"
        elements.append({
            "path": rel_path,
            "name": name,
            "type": "class",
            "text": text,
        })

    return elements


def _extract_js_ts_elements(content: str, rel_path: str) -> list[dict]:
    """Extract JavaScript/TypeScript functions using regex."""
    import re
    elements = []

    # Named functions and arrow functions
    patterns = [
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
        r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',
        r'(?:export\s+)?class\s+(\w+)',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content, re.MULTILINE):
            name = match.group(1)
            # Get context (surrounding lines)
            start = max(0, content[:match.start()].rfind("\n"))
            end = content.find("\n", match.end())
            context = content[start:end].strip() if end > 0 else content[start:].strip()

            elements.append({
                "path": rel_path,
                "name": name,
                "type": "function" if "class" not in pattern else "class",
                "text": context,
            })

    return elements


def _extract_go_elements(content: str, rel_path: str) -> list[dict]:
    """Extract Go functions and types using regex."""
    import re
    elements = []

    for match in re.finditer(r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(([^)]*)\)', content):
        name = match.group(1)
        params = match.group(2)
        elements.append({
            "path": rel_path,
            "name": name,
            "type": "function",
            "text": f"func {name}({params})",
        })

    for match in re.finditer(r'type\s+(\w+)\s+struct', content):
        name = match.group(1)
        elements.append({
            "path": rel_path,
            "name": name,
            "type": "struct",
            "text": f"type {name} struct",
        })

    return elements


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    import re
    # Split on non-alphanumeric, lowercase
    tokens = re.findall(r'\w+', text.lower())
    # Filter very short tokens
    return [t for t in tokens if len(t) > 1]
