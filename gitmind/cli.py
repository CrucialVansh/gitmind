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

import asyncio
import json
import sys

import click
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

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
    """
    from gitmind.db import GitMindDB
    from gitmind.parsers.git_parser import parse_commits
    from gitmind.parsers.session_parser import parse_cursor_sessions, chunk_session
    from gitmind.linker import link_all

    console.print(Panel(
        Text("🔍 Indexing repository...", style="bold cyan"),
        subtitle=f"[dim]{repo_path.resolve()}[/dim]",
    ))

    db = GitMindDB()
    db.create_tables()

    # Step 1: Parse git commits
    commits = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Parsing git history...", total=None)
        for commit in parse_commits(repo_path):
            if since:
                from datetime import datetime
                cutoff = datetime.fromisoformat(since)
                if commit.timestamp.replace(tzinfo=None) < cutoff:
                    continue
            commits.append(commit)
            db.insert_commit(commit)
        progress.update(task, description=f"✅ Parsed {len(commits)} commits")

    console.print(f"  📝 Indexed [bold]{len(commits)}[/bold] commits")

    # Step 2: Parse sessions
    sessions = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Discovering AI sessions...", total=None)

        if session_source in ("cursor", "all"):
            try:
                cursor_sessions = list(parse_cursor_sessions())
                for s in cursor_sessions:
                    s.chunks = chunk_session(s)
                    db.insert_session(s)
                    sessions.append(s)
            except Exception as e:
                console.print(f"  [dim]⚠ Cursor sessions: {e}[/dim]")

        progress.update(
            task,
            description=f"✅ Found {len(sessions)} sessions",
        )

    console.print(f"  💬 Indexed [bold]{len(sessions)}[/bold] sessions")

    # Step 3: Link commits to sessions
    if commits and sessions:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Linking commits to sessions...", total=None)
            pairs = link_all(commits, sessions)
            for pair in pairs:
                db.insert_pair(pair)
            progress.update(
                task,
                description=f"✅ Created {len(pairs)} links",
            )
        console.print(f"  🔗 Created [bold]{len(pairs)}[/bold] commit-session links")
    else:
        console.print("  [dim]⚠ No links created (need both commits and sessions)[/dim]")

    # Summary
    stats = db.stats()
    console.print()
    console.print(Panel(
        f"[bold green]✅ Indexing complete![/bold green]\n"
        f"  Commits: {stats['commits']}  |  Sessions: {stats['sessions']}  |  "
        f"Chunks: {stats['chunks']}  |  Links: {stats['pairs']}",
        title="Summary",
    ))


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
    """
    from gitmind.answer import answer as answer_fn

    console.print(f"[bold]Query:[/bold] {query}")
    console.print("[dim]Routing query...[/dim]")

    result = asyncio.run(answer_fn(query, str(repo.resolve())))

    if output_json:
        click.echo(result.model_dump_json(indent=2))
        return

    # Rich formatted output
    console.print()
    console.print(Panel(
        result.answer,
        title=f"[bold]Answer[/bold] [dim]({result.intent.value})[/dim]",
        border_style="green",
    ))

    # Decision arc timeline
    if result.decision_arc:
        console.print()
        table = Table(title="Decision Timeline")
        table.add_column("Date", style="cyan")
        table.add_column("Commit", style="yellow")
        table.add_column("Rationale", style="white")

        for entry in result.decision_arc:
            table.add_row(
                entry.date.strftime("%Y-%m-%d"),
                entry.commit_hash[:7],
                entry.rationale_summary[:80],
            )
        console.print(table)

    # Sources
    if result.source_commits or result.source_sessions:
        sources = []
        if result.source_commits:
            sources.append(f"commits: {', '.join(h[:7] for h in result.source_commits)}")
        if result.source_sessions:
            sources.append(f"sessions: {', '.join(result.source_sessions)}")
        console.print(f"\n[dim]Sources: {' · '.join(sources)}[/dim]")

    if result.token_count:
        console.print(f"[dim]Tokens used: {result.token_count}[/dim]")


# ── gitmind search ─────────────────────────────────────────────────────────────

@cli.command()
@click.argument("term")
@click.option("--top", default=5, show_default=True, help="Number of results to return.")
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to the repository. Defaults to current directory.",
)
def search(term: str, top: int, repo: Path):
    """
    Search for session chunks mentioning a topic or keyword.

    Example:
      gitmind search "rate limiting"
      gitmind search "retry logic"
    """
    from gitmind.retrieval.structural import StructuralIndex
    from gitmind.retrieval.episodes import EpisodeStore

    console.print(f"[bold]Searching for:[/bold] {term}")

    results_found = False

    # Search structural index
    struct_index = StructuralIndex()
    struct_index.load()

    if struct_index._bm25 is None:
        # Try building on the fly
        struct_index.build(repo)

    struct_results = struct_index.search(term, top_k=top)
    if struct_results:
        results_found = True
        console.print()
        table = Table(title="Code Structure Results")
        table.add_column("Type", style="cyan")
        table.add_column("Path", style="yellow")
        table.add_column("Name", style="green")
        table.add_column("Score", style="dim")

        for r in struct_results:
            table.add_row(r["type"], r["path"], r["name"], f"{r['score']:.2f}")
        console.print(table)

    # Search episode store
    try:
        episode_store = EpisodeStore()
        episode_store.load()

        if episode_store._index is not None:
            episode_results = episode_store.search(term, top_k=top)
            gated_results = [r for r in episode_results if r.passed_gate]

            if gated_results:
                results_found = True
                console.print()
                table = Table(title="Session Results")
                table.add_column("Session", style="cyan")
                table.add_column("Score", style="yellow")
                table.add_column("Text", style="white", max_width=60)

                for r in gated_results:
                    table.add_row(
                        r.chunk.session_id,
                        f"{r.score:.2f}",
                        r.chunk.text[:60] + "..." if len(r.chunk.text) > 60 else r.chunk.text,
                    )
                console.print(table)
    except Exception as e:
        console.print(f"[dim]Episode search skipped: {e}[/dim]")

    if not results_found:
        console.print("[yellow]No results found. Try running 'gitmind index' first.[/yellow]")


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
    """
    from gitmind.db import GitMindDB
    from gitmind.parsers.session_parser import parse_claude_export, chunk_session

    console.print(f"[bold]Importing Claude export:[/bold] {json_path}")

    db = GitMindDB()
    db.create_tables()

    count = 0
    for session in parse_claude_export(json_path):
        session.chunks = chunk_session(session)
        db.insert_session(session)
        count += 1

    console.print(f"[green]✅ Imported {count} sessions from Claude export[/green]")


@import_.command(name="transcript")
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
def import_transcript(file_path: Path):
    """Import a manually exported transcript (plain text or markdown)."""
    from gitmind.db import GitMindDB
    from gitmind.parsers.session_parser import parse_manual_transcript, chunk_session

    console.print(f"[bold]Importing transcript:[/bold] {file_path}")

    db = GitMindDB()
    db.create_tables()

    session = parse_manual_transcript(file_path)
    session.chunks = chunk_session(session)
    db.insert_session(session)

    console.print(
        f"[green]✅ Imported session '{session.session_id}' "
        f"({len(session.chunks)} chunks, "
        f"{len(session.files_mentioned)} files mentioned)[/green]"
    )


# ── gitmind status ─────────────────────────────────────────────────────────────

@cli.command()
def status():
    """
    Show the health of the GitMind index.

    Displays:
      - Number of indexed commits
      - Number of indexed sessions and chunks
      - Number of commit-session pairs
      - Data directory location
    """
    from gitmind.config import settings
    from gitmind.db import GitMindDB

    db = GitMindDB()

    # Check if DB exists
    if not settings.db_path.exists():
        console.print(Panel(
            "[yellow]No GitMind index found.[/yellow]\n"
            f"Run [bold]gitmind index[/bold] in a git repository to get started.\n"
            f"Data directory: [dim]{settings.data_dir}[/dim]",
            title="GitMind Status",
        ))
        return

    stats = db.stats()

    table = Table(title="GitMind Index Health")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="bold green", justify="right")

    table.add_row("📝 Commits", str(stats["commits"]))
    table.add_row("💬 Sessions", str(stats["sessions"]))
    table.add_row("📄 Chunks", str(stats["chunks"]))
    table.add_row("🔗 Commit-Session Links", str(stats["pairs"]))

    console.print(table)

    # Additional info
    console.print(f"\n[dim]Data directory: {settings.data_dir}[/dim]")
    console.print(f"[dim]Database: {settings.db_path}[/dim]")

    if settings.faiss_index_path.exists():
        size = settings.faiss_index_path.stat().st_size / 1024
        console.print(f"[dim]FAISS index: {settings.faiss_index_path} ({size:.1f} KB)[/dim]")

    if settings.bm25_index_path.exists():
        size = settings.bm25_index_path.stat().st_size / 1024
        console.print(f"[dim]BM25 index: {settings.bm25_index_path} ({size:.1f} KB)[/dim]")


# ── Entry point ────────────────────────────────────────────────────────────────

# Register the import group under the right name
cli.add_command(import_, name="import")

if __name__ == "__main__":
    cli()
