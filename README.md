# GitMind 🧠

[![CI](https://github.com/CrucialVansh/gitmind/actions/workflows/pylint.yml/badge.svg)](https://github.com/CrucialVansh/gitmind/actions/workflows/pylint.yml)
[![PyPI version](https://img.shields.io/pypi/v/gitmind.svg)](https://pypi.org/project/gitmind/)
[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://pypi.org/project/gitmind/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

> **Git-bound coding agent memory.** Makes your team's AI session reasoning permanent and searchable.

Every architectural decision your team made in a Cursor or Claude session vanishes when that session closes. GitMind mines your git history + AI transcripts to reconstruct *why* your codebase looks the way it does — and makes it queryable in under a second.

```bash
$ gitmind ask "why does fetchUserWithRetry only retry on 503, not 429?"

[Nov 2025] Claude session: Vendor confirmed 429s are client-side violations
           and should NOT be auto-retried — doing so would trigger an API ban.
           503s are transient server errors safe to retry.

[Jan 2026] Claude session: Raised retry count to 7 based on SLA data showing
           99.9% of 503s resolve within 6 attempts.

Sources: commits a3f2c1d, e9b7f2a · sessions 2025-11-14, 2026-01-08
```

---

## Installation

```bash
pip install gitmind
```

---

## Quick Start

```bash
# 1. Index your repo (walks git log, extracts AST touched functions, links Cursor/Claude sessions)
cd your-project/
gitmind index

# 2. Ask questions about your codebase decisions (routes to Structural, Rationale, or Episode strategy)
gitmind ask "why did we switch from REST to gRPC?"
gitmind ask "why is the cache TTL set to 300 seconds?"
gitmind ask "where does the retry logic live?"
gitmind ask "what alternatives did we consider for the auth system?"

# 3. Search for specific sessions or code structures
gitmind search "rate limiting"
gitmind search "fetchUser" --text

# 4. Check index health and stats
gitmind status
```

---

## VS Code Extension 🧩

GitMind includes a native VS Code extension located in [`vscode-gitmind/`](vscode-gitmind/):

- **Sidebar Webview Panel**: Ask questions directly inside your IDE with interactive decision timelines and cited commits.
- **Function CodeLens**: Shows `🧠 GitMind Rationale: <function>` above functions to quickly inspect past decisions.
- **Hover Provider**: Hover over function definitions to jump directly to its rationale arc.

### Install & Build Extension
```bash
cd vscode-gitmind
npm install
npm run build
```

---

## Session Sources Supported

| Source | Storage Format | How to connect |
|--------|----------------|----------------|
| **Cursor** | `state.vscdb` (`cursorDiskKV` & `ItemTable`) | Auto-detected from `~/Library/Application Support/Cursor/User/workspaceStorage/` or `~/.config/Cursor/User/` |
| **Claude Projects** | JSON export (`conversations.json`) | `gitmind import claude path/to/conversations.json` |
| **Manual transcripts** | Markdown / Plain text | `gitmind import transcript path/to/session.md` |

---

## Architecture

```
git log + AI sessions
        ↓
  Commit-Session Linker  (timestamp + filepath overlap, zero human annotation)
        ↓
  ┌─────────────────────────────────────┐
  │  Structural Index   Episode Store   │
  │  (BM25 over AST)   (FAISS + gate)  │
  └─────────────────────────────────────┘
        ↓
  Intent Router  →  Confidence Gate  →  Decision Synthesizer  →  LLM Answer
```

- **Commit Parser**: Extracts unified diffs, modified line ranges, and functions touched via **Tree-sitter AST queries** (`tree-sitter-python`, `tree-sitter-typescript`).
- **Commit-Session Linker**: Zero-label correlation linking commits with AI conversations using time windows and filepath overlap scores.
- **Retrieval Engine**:
  - `structural.py`: BM25Plus index over code symbols, docstrings, and signatures.
  - `episodes.py`: FAISS vector index with an empirical **confidence gate** threshold (drops low-similarity chunks to prevent hallucinations).
  - `synthesizer.py`: Reconstructs chronological "why-arcs" across commits touching specific functions.
- **Intent Router**: Regex-based sub-millisecond query intent classification (`RATIONALE`, `STRUCTURAL`, `EPISODE`).

---

## Development

```bash
git clone https://github.com/CrucialVansh/gitmind.git
cd gitmind
pip install -e ".[dev]"
pytest
```

---

## Project Status

- [x] Week 1: Data pipeline (git parser, session parser, commit-session linker)
- [x] Week 2: Retrieval system (BM25Plus over AST, FAISS, confidence gate)
- [x] Week 3: Query router + answer assembly + CLI
- [x] Week 4: Tree-sitter AST extraction + VS Code extension + PyPI packaging

---

## License

MIT © [Vansh Pruthi](https://github.com/CrucialVansh)
