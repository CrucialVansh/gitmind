"""
GitMind CLI — the user-facing entry point.

Commands:
  gitmind index          Index (or re-index) the current git repository
  gitmind ask  <query>   Ask a question about a codebase decision
  gitmind search <term>  Search for sessions mentioning a topic
  gitmind import         Import session transcripts from Claude/manual sources
  gitmind status         Show index health (row counts, last indexed, etc.)

Built with Click + Rich for a polished terminal experience.
"""

import click
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


@click.group()
@click.version_option(package_name="gitmind")
def cli():
    """
    🧠 GitMind — Git-bound coding agent memory.

    Makes your team's AI session reasoning permanent and searchable.
    """
    pass


# ── gitmind index ──────────────────────────────────────────────────────────────

@cli.command()
@click.argument(
    "repo_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--since",
    default=None,
    help="Only index commits after this date (e.g. '2025-01-01'). Defaults to all history.",
)
@click.option(
    "--session-source",
    type=click.Choice(["cursor", "claude", "all"], case_sensitive=False),
    default="all",
    show_default=True,
    help="Which session sources to index.",
)
def index(repo_path: Path, since: str | None, session_source: str):
    """
    Index the git repository and AI sessions at REPO_PATH.

    This command:
      1. Parses git commit history
      2. Discovers and parses AI session transcripts
      3. Links commits to sessions (the zero-label trick)
      4. Stores everything in ~/.gitmind/store.db

    Run this once, then again whenever you have new commits or sessions.

    TODO (Week 1): wire up git_parser, session_parser, linker, and db here.
    """
    console.print(Panel(
        Text("🔍 Indexing repository...", style="bold cyan"),
        subtitle=f"[dim]{repo_path.resolve()}[/dim]",
    ))
    raise NotImplementedError(
        "Week 1: implement index command — call git_parser, session_parser, linker, db"
    )


# ── gitmind ask ───────────────────────────────────────────────────────────────

@cli.command()
@click.argument("query")
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to the repository to query. Defaults to current directory.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output the result as JSON (for VS Code extension integration).",
)
def ask(query: str, repo: Path, output_json: bool):
    """
    Ask a question about a codebase decision.

    Examples:
      gitmind ask "why does fetchUserWithRetry only retry on 503?"
      gitmind ask "why did we switch from REST to gRPC?"
      gitmind ask "what alternatives did we consider for the auth system?"

    TODO (Week 3): wire up router → retrieval → answer assembly here.
    """
    console.print(f"[bold]Query:[/bold] {query}")
    console.print("[dim]Routing query...[/dim]")
    raise NotImplementedError("Week 3: implement ask command")


# ── gitmind search ─────────────────────────────────────────────────────────────

@cli.command()
@click.argument("term")
@click.option("--top", default=5, show_default=True, help="Number of results to return.")
def search(term: str, top: int):
    """
    Search for session chunks mentioning a topic or keyword.

    Example:
      gitmind search "rate limiting"
      gitmind search "retry logic"

    TODO (Week 2): implement using BM25 structural index + episode store.
    """
    console.print(f"[bold]Searching for:[/bold] {term}")
    raise NotImplementedError("Week 2: implement search command")


# ── gitmind import ─────────────────────────────────────────────────────────────

@cli.group()
def import_():
    """Import session transcripts from external sources."""
    pass


@import_.command(name="claude")
@click.argument("json_path", type=click.Path(exists=True, path_type=Path))
def import_claude(json_path: Path):
    """
    Import a Claude Projects conversation export (JSON).

    To export: Claude.ai → Project → ··· → Export conversations → JSON

    TODO (Week 1): call session_parser.parse_claude_export() here.
    """
    console.print(f"[bold]Importing Claude export:[/bold] {json_path}")
    raise NotImplementedError("Week 1: implement import claude command")


@import_.command(name="transcript")
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
def import_transcript(file_path: Path):
    """
    Import a manually exported transcript (plain text or markdown).

    TODO (Week 1): call session_parser.parse_manual_transcript() here.
    """
    console.print(f"[bold]Importing transcript:[/bold] {file_path}")
    raise NotImplementedError("Week 1: implement import transcript command")


# ── gitmind status ─────────────────────────────────────────────────────────────

@cli.command()
def status():
    """
    Show the health of the GitMind index.

    Displays:
      - Number of indexed commits
      - Number of indexed sessions and chunks
      - Number of commit-session pairs
      - Last index time
      - Data directory location

    TODO (Week 1): call db.stats() here and display with a rich Table.
    """
    raise NotImplementedError("Week 1: implement status command")


# ── Entry point ────────────────────────────────────────────────────────────────

# Register the import group under the right name
cli.add_command(import_, name="import")

if __name__ == "__main__":
    cli()
