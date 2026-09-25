"""
Tests for gitmind/retrieval/structural.py and gitmind/parsers/ast_extractor.py

Run with:  pytest tests/test_structural.py -v
"""


from gitmind.config import settings
from gitmind.parsers.ast_extractor import (
    extract_symbols,
    find_touched_functions,
)
from gitmind.retrieval.structural import StructuralIndex


# ── AST Extraction Tests ──────────────────────────────────────────────────────

def test_extract_symbols_python():
    code = """
def calculate_metrics(data: list[int]) -> dict:
    \"\"\"Calculate summary metrics.\"\"\"
    return {"mean": sum(data) / len(data)}

class MetricsEngine:
    \"\"\"Engine for computing metrics.\"\"\"
    def run(self):
        pass
"""
    symbols = extract_symbols(code, ".py")
    names = [s.name for s in symbols]

    assert "calculate_metrics" in names
    assert "MetricsEngine" in names
    assert "run" in names

    # Check symbol types
    calc_sym = next(s for s in symbols if s.name == "calculate_metrics")
    assert calc_sym.symbol_type == "function"
    assert calc_sym.start_line == 2

    engine_sym = next(s for s in symbols if s.name == "MetricsEngine")
    assert engine_sym.symbol_type == "class"


def test_extract_symbols_typescript():
    code = """
export function authenticateUser(token: string): boolean {
    return token.length > 0;
}

export class AuthService {
    verifySession(id: string) {
        return true;
    }
}
"""
    symbols = extract_symbols(code, ".ts")
    names = [s.name for s in symbols]

    assert "authenticateUser" in names
    assert "AuthService" in names
    assert "verifySession" in names


def test_find_touched_functions():
    code = """
def func_a():
    return 1

def func_b():
    return 2

def func_c():
    return 3
"""
    symbols = extract_symbols(code, ".py")
    # func_b is around lines 5-6
    modified_ranges = [(5, 6)]

    touched = find_touched_functions(symbols, modified_ranges)
    assert "func_b" in touched
    assert "func_a" not in touched
    assert "func_c" not in touched


# ── Structural Index Tests ───────────────────────────────────────────────────

def test_structural_index_build_and_search(tmp_path):
    # Create sample files
    py_file = tmp_path / "service.py"
    py_file.write_text("""
def handleRateLimit():
    \"\"\"Handles 429 and rate limiting with exponential backoff.\"\"\"
    pass

def fetchUserWithRetry():
    \"\"\"Retries on 503 server errors only.\"\"\"
    pass
""")

    index = StructuralIndex()
    index.build(tmp_path)

    # Search for retry
    results = index.search("retry logic 503", top_k=3)
    assert len(results) > 0
    names = [r["name"] for r in results]
    assert any("fetchUserWithRetry" in n or "service.py" in n for n in names)

    # Search for rate limit
    results_rl = index.search("rate limiting exponential backoff", top_k=3)
    assert len(results_rl) > 0
    names_rl = [r["name"] for r in results_rl]
    assert any("handleRateLimit" in n or "service.py" in n for n in names_rl)


def test_structural_index_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    py_file = tmp_path / "test_module.py"
    py_file.write_text("def mySpecialUniqueFunction(): pass")

    index = StructuralIndex()
    index.build(tmp_path)
    index.save()

    new_index = StructuralIndex()
    new_index.load()

    results = new_index.search("mySpecialUniqueFunction")
    assert len(results) > 0
    assert any("mySpecialUniqueFunction" in r["name"] for r in results)
