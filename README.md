# GitMind 🧠

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

## Quick Start

```bash
# 1. Index your repo (run once, then on new commits)
cd your-project/
gitmind index

# 2. Ask questions about your codebase decisions
gitmind ask "why did we switch from REST to gRPC?"
gitmind ask "why is the cache TTL set to 300 seconds?"
gitmind ask "what alternatives did we consider for the auth system?"

# 3. Search for specific sessions
gitmind search "rate limiting"
```

## Session Sources Supported

| Source | How to connect |
|--------|----------------|
| Cursor | Auto-detected from `~/.cursor/User/workspaceStorage/` |
| Claude Projects | Export JSON → `gitmind import claude path/to/export.json` |
| Manual transcript | `gitmind import transcript path/to/session.md` |

---

## Architecture

```
git log + AI sessions
        ↓
  Commit-Session Linker  (timestamp + filepath overlap)
        ↓
  ┌─────────────────────────────────────┐
  │  Structural Index   Episode Store   │
  │  (BM25 over AST)   (FAISS + gate)  │
  └─────────────────────────────────────┘
        ↓
  Intent Router  →  Confidence Gate  →  LLM Answer
```

---

## Development

```bash
git clone https://github.com/you/gitmind
cd gitmind
pip install -e ".[dev]"
pytest
```

## Project Status

- [x] Week 1: Data pipeline (git parser, session parser, commit-session linker)
- [ ] Week 2: Retrieval system (BM25, FAISS, confidence gate)
- [ ] Week 3: Query router + answer assembly
- [ ] Week 4: VS Code extension + PyPI publish

---

## License

MIT
