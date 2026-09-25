"""
AST and Code Structure Extractor.

Uses Tree-sitter (with regex fallback) to extract function, method, and class
definitions and their line ranges.

Also provides diff-hunk analysis to detect which functions were modified
in a git commit.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Tree-sitter parsers and queries (lazy loaded)
_PARSERS: dict[str, tuple] = {}


@dataclass
class CodeSymbol:
    """A function, method, or class extracted from source code."""
    name: str
    symbol_type: str  # "function", "class", "method", "struct"
    start_line: int  # 1-indexed
    end_line: int    # 1-indexed
    docstring: Optional[str] = None
    signature: Optional[str] = None


def _get_tree_sitter_env(file_extension: str):
    """
    Get or create (parser, query) for a given file extension.
    Returns None if tree-sitter is not supported for this extension.
    """
    ext = file_extension.lower()
    if ext in _PARSERS:
        return _PARSERS[ext]

    try:
        from tree_sitter import Language, Parser, Query

        if ext == ".py":
            import tree_sitter_python as tspython
            lang = Language(tspython.language())
            query = Query(
                lang,
                """
                (function_definition name: (identifier) @name) @func
                (class_definition name: (identifier) @name) @class
                """,
            )
            parser = Parser(lang)
            _PARSERS[ext] = (parser, query, "python")
            return _PARSERS[ext]

        if ext in (".ts", ".js"):
            import tree_sitter_typescript as tstypescript
            lang = Language(tstypescript.language_typescript())
            query = Query(
                lang,
                """
                (function_declaration name: (identifier) @name) @func
                (variable_declarator name: (identifier) @name value: (arrow_function)) @func
                (method_definition name: (property_identifier) @name) @func
                (class_declaration name: (type_identifier) @name) @class
                """,
            )
            parser = Parser(lang)
            _PARSERS[ext] = (parser, query, "typescript")
            return _PARSERS[ext]

        if ext in (".tsx", ".jsx"):
            import tree_sitter_typescript as tstypescript
            lang = Language(tstypescript.language_tsx())
            query = Query(
                lang,
                """
                (function_declaration name: (identifier) @name) @func
                (variable_declarator name: (identifier) @name value: (arrow_function)) @func
                (method_definition name: (property_identifier) @name) @func
                (class_declaration name: (type_identifier) @name) @class
                """,
            )
            parser = Parser(lang)
            _PARSERS[ext] = (parser, query, "tsx")
            return _PARSERS[ext]

    except Exception as e:
        logger.debug("Tree-sitter setup failed for %s: %s", ext, e)

    return None


def extract_symbols(source_code: str | bytes, file_extension: str) -> list[CodeSymbol]:
    """
    Extract functions and classes from source code with line ranges.
    Uses tree-sitter where available; falls back to regex.
    """
    if isinstance(source_code, str):
        code_bytes = source_code.encode("utf-8", errors="replace")
        code_str = source_code
    else:
        code_bytes = source_code
        code_str = source_code.decode("utf-8", errors="replace")

    env = _get_tree_sitter_env(file_extension)
    if env is not None:
        try:
            return _extract_symbols_treesitter(code_bytes, env)
        except Exception as e:
            logger.debug("Tree-sitter extraction failed: %s, falling back to regex", e)

    return _extract_symbols_regex(code_str, file_extension)


def _extract_symbols_treesitter(code_bytes: bytes, env: tuple) -> list[CodeSymbol]:
    """Extract symbols using Tree-sitter."""
    from tree_sitter import QueryCursor

    parser, query, _lang_name = env
    tree = parser.parse(code_bytes)
    cursor = QueryCursor(query)
    matches = cursor.matches(tree.root_node)

    symbols: list[CodeSymbol] = []
    lines = code_bytes.splitlines()

    for _pattern_idx, match_dict in matches:
        name_nodes = match_dict.get("name", [])
        if not name_nodes:
            continue
        name_node = name_nodes[0]
        symbol_name = name_node.text.decode("utf-8", errors="replace")

        full_node = match_dict.get("func", [None])[0] or match_dict.get("class", [None])[0]
        if full_node is None:
            full_node = name_node

        start_line = full_node.start_point[0] + 1  # 1-indexed
        end_line = full_node.end_point[0] + 1

        sym_type = "class" if "class" in match_dict else "function"

        # Extract docstring / signature preview
        sig_line = (
            lines[start_line - 1].decode("utf-8", errors="replace").strip()
            if start_line - 1 < len(lines)
            else ""
        )
        docstring = _extract_docstring_preview(lines, start_line, end_line)

        symbols.append(
            CodeSymbol(
                name=symbol_name,
                symbol_type=sym_type,
                start_line=start_line,
                end_line=end_line,
                docstring=docstring,
                signature=sig_line,
            )
        )

    return symbols


def _extract_docstring_preview(lines: list[bytes], start_line: int, end_line: int) -> Optional[str]:
    """Look for docstrings right below function/class start."""
    for i in range(start_line, min(start_line + 5, end_line, len(lines))):
        line = lines[i].decode("utf-8", errors="replace").strip()
        if line.startswith(('"""', "'''")):
            return line.strip("\"' ")
    return None


def _extract_symbols_regex(content: str, suffix: str) -> list[CodeSymbol]:
    """Fallback symbol extraction using regular expressions."""
    symbols: list[CodeSymbol] = []
    lines = content.splitlines()

    if suffix == ".py":
        for i, line in enumerate(lines):
            func_m = re.match(r'^[ \t]*(?:async\s+)?def\s+([a-zA-Z0-9_]+)\s*\(', line)
            if func_m:
                symbols.append(
                    CodeSymbol(
                        name=func_m.group(1),
                        symbol_type="function",
                        start_line=i + 1,
                        end_line=i + 20,  # approximate
                        signature=line.strip(),
                    )
                )
            class_m = re.match(r'^[ \t]*class\s+([a-zA-Z0-9_]+)', line)
            if class_m:
                symbols.append(
                    CodeSymbol(
                        name=class_m.group(1),
                        symbol_type="class",
                        start_line=i + 1,
                        end_line=i + 30,  # approximate
                        signature=line.strip(),
                    )
                )

    elif suffix in (".ts", ".tsx", ".js", ".jsx"):
        for i, line in enumerate(lines):
            fn_m = re.match(
                r'^[ \t]*(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_]+)', line
            )
            if not fn_m:
                fn_m = re.match(
                    r'^[ \t]*(?:export\s+)?(?:const|let|var)\s+'
                    r'([a-zA-Z0-9_]+)\s*=\s*(?:async\s+)?\(',
                    line,
                )
            if fn_m:
                symbols.append(
                    CodeSymbol(
                        name=fn_m.group(1),
                        symbol_type="function",
                        start_line=i + 1,
                        end_line=i + 20,
                        signature=line.strip(),
                    )
                )
            cl_m = re.match(r'^[ \t]*(?:export\s+)?class\s+([a-zA-Z0-9_]+)', line)
            if cl_m:
                symbols.append(
                    CodeSymbol(
                        name=cl_m.group(1),
                        symbol_type="class",
                        start_line=i + 1,
                        end_line=i + 30,
                        signature=line.strip(),
                    )
                )

    return symbols


# ── Diff Hunk Analysis ────────────────────────────────────────────────────────


def parse_diff_modified_lines(diff_text: str) -> dict[str, list[tuple[int, int]]]:
    """
    Parse a unified diff and return modified line ranges (start, end) per file.
    Hunk headers: @@ -old_start,old_len +new_start,new_len @@
    """
    file_ranges: dict[str, list[tuple[int, int]]] = {}
    current_file: Optional[str] = None

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            if current_file not in file_ranges:
                file_ranges[current_file] = []
        elif line.startswith("@@ ") and current_file:
            # Match @@ -a,b +c,d @@ or @@ -a +c @@
            m = re.search(r'\+(\d+)(?:,(\d+))?', line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) is not None else 1
                end = start + max(1, count) - 1
                file_ranges[current_file].append((start, end))

    return file_ranges


def find_touched_functions(
    symbols: list[CodeSymbol],
    modified_ranges: list[tuple[int, int]],
) -> list[str]:
    """
    Given symbols in a file and modified line ranges from diff,
    return names of functions/classes that overlap with the modified lines.
    """
    touched: list[str] = []

    for sym in symbols:
        for mod_start, mod_end in modified_ranges:
            # Overlap check: max(start1, start2) <= min(end1, end2)
            if max(sym.start_line, mod_start) <= min(sym.end_line, mod_end):
                if sym.name not in touched:
                    touched.append(sym.name)
                break

    return touched
