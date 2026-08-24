"""
Answer assembler — Week 3.

Takes retrieved context (structural results / episode chunks / decision arc)
and generates a final natural-language answer via GPT-4o mini.

Pipeline: route query → retrieve context → generate answer
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from gitmind.config import settings
from gitmind.db import GitMindDB
from gitmind.models import (
    DecisionArcEntry,
    QueryIntent,
    QueryResult,
    RetrievedChunk,
)
from gitmind.retrieval.episodes import EpisodeStore
from gitmind.retrieval.structural import StructuralIndex
from gitmind.retrieval.synthesizer import DecisionSynthesizer
from gitmind.router import route

logger = logging.getLogger(__name__)


async def answer(query: str, repo_path: str) -> QueryResult:
    """
    Full pipeline: route query → retrieve context → generate answer.

    This is the top-level function called by the CLI `ask` command.

    Args:
        query: The user's natural language question.
        repo_path: Path to the git repository.

    Returns:
        A fully populated QueryResult.
    """
    # Step 1: Route the query
    intent = route(query)
    logger.info("Query intent: %s", intent.value)

    # Step 2: Retrieve context based on intent
    context_parts: list[str] = []
    source_commits: list[str] = []
    source_sessions: list[str] = []
    decision_arc: list[DecisionArcEntry] = []

    db = GitMindDB()

    if intent == QueryIntent.STRUCTURAL:
        context_parts, source_commits = _retrieve_structural(query, repo_path)

    elif intent == QueryIntent.RATIONALE:
        context_parts, source_commits, source_sessions, decision_arc = (
            _retrieve_rationale(query, db)
        )

    elif intent == QueryIntent.EPISODE:
        context_parts, source_sessions = _retrieve_episodes(query)

    # Step 3: Generate answer
    answer_text, token_count = await _generate_answer(query, intent, context_parts)

    return QueryResult(
        query=query,
        intent=intent,
        answer=answer_text,
        decision_arc=decision_arc,
        source_commits=source_commits,
        source_sessions=source_sessions,
        token_count=token_count,
    )


def _retrieve_structural(query: str, repo_path: str) -> tuple[list[str], list[str]]:
    """Retrieve structural context using BM25 index."""
    index = StructuralIndex()
    index.load()

    # If no index exists, try to build one
    if index._bm25 is None:
        index.build(Path(repo_path))

    results = index.search(query, top_k=5)

    context_parts = []
    source_commits = []
    for r in results:
        context_parts.append(
            f"[{r['type']}] {r['path']} → {r['name']}\n{r['text']}"
        )

    return context_parts, source_commits


def _retrieve_rationale(
    query: str, db: GitMindDB
) -> tuple[list[str], list[str], list[str], list[DecisionArcEntry]]:
    """Retrieve rationale context using the Decision Synthesizer."""
    # Extract the function/topic name from the query
    function_name = _extract_function_name(query)

    synthesizer = DecisionSynthesizer(db)
    arc = synthesizer.synthesize(query, function_name)

    context_parts = []
    source_commits = []
    source_sessions = []

    for entry in arc:
        context_parts.append(
            f"[{entry.date.strftime('%Y-%m-%d')}] commit {entry.commit_hash[:7]}: "
            f"{entry.rationale_summary}"
        )
        source_commits.append(entry.commit_hash)

    # Also search episodes for additional context
    episode_context, episode_sessions = _retrieve_episodes(query)
    context_parts.extend(episode_context)
    source_sessions.extend(episode_sessions)

    return context_parts, source_commits, source_sessions, arc


def _retrieve_episodes(query: str) -> tuple[list[str], list[str]]:
    """Retrieve episode context using FAISS with confidence gate."""
    store = EpisodeStore()
    store.load()

    if store._index is None:
        return [], []

    results = store.search(query, top_k=10)

    context_parts = []
    source_sessions = []

    for r in results:
        if r.passed_gate:
            context_parts.append(
                f"[Session {r.chunk.session_id}] (score: {r.score:.2f})\n{r.chunk.text}"
            )
            if r.chunk.session_id not in source_sessions:
                source_sessions.append(r.chunk.session_id)

    return context_parts, source_sessions


async def _generate_answer(
    query: str,
    intent: QueryIntent,
    context_parts: list[str],
) -> tuple[str, int]:
    """
    Generate a natural language answer using the OpenAI API.

    Falls back to a context-only summary if no API key is configured.
    """
    if not context_parts:
        return (
            "No relevant context found in the indexed sessions and commits. "
            "Try running `gitmind index` to ensure your repository is indexed.",
            0,
        )

    context_text = "\n\n---\n\n".join(context_parts)

    # If no API key, return the raw context
    if not settings.openai_api_key:
        fallback = f"**Found {len(context_parts)} relevant context(s):**\n\n"
        for i, part in enumerate(context_parts, 1):
            fallback += f"**{i}.** {part}\n\n"
        return fallback, 0

    # Call OpenAI
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)

        system_prompt = _build_system_prompt(intent)

        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Question: {query}\n\nContext from git history and AI sessions:\n\n{context_text}",
                },
            ],
            temperature=0.3,
            max_tokens=1000,
        )

        answer_text = response.choices[0].message.content or "No answer generated."
        token_count = response.usage.total_tokens if response.usage else 0

        return answer_text, token_count

    except ImportError:
        logger.warning("openai package not installed — returning raw context")
        return f"(OpenAI not available)\n\n{context_text}", 0
    except Exception as e:
        logger.error("OpenAI API error: %s", e)
        return f"Error generating answer: {e}\n\nRaw context:\n{context_text}", 0


def _build_system_prompt(intent: QueryIntent) -> str:
    """Build the system prompt based on query intent."""
    base = (
        "You are GitMind, an AI that answers questions about codebase decisions "
        "by analyzing git commit history and AI coding session transcripts. "
        "Always cite specific commits and sessions when possible. "
        "Be concise but thorough."
    )

    if intent == QueryIntent.RATIONALE:
        return (
            f"{base}\n\n"
            "The user is asking WHY a decision was made. "
            "Focus on the reasoning, alternatives considered, and the decision timeline. "
            "Present the answer chronologically if multiple decisions were made over time."
        )
    elif intent == QueryIntent.STRUCTURAL:
        return (
            f"{base}\n\n"
            "The user is asking WHERE something is in the codebase. "
            "Focus on file paths, function names, and code structure. "
            "Be specific about locations."
        )
    else:
        return (
            f"{base}\n\n"
            "The user is asking about a topic or event in the codebase history. "
            "Summarize the relevant information from the sessions and commits."
        )


def _extract_function_name(query: str) -> str:
    """Extract a likely function/symbol name from the query."""
    # Look for camelCase or snake_case identifiers
    matches = re.findall(r'[a-z]+(?:[A-Z][a-z]+)+|[a-z]+(?:_[a-z]+)+', query)
    if matches:
        return matches[0]

    # Look for quoted terms
    quoted = re.findall(r'["\']([^"\']+)["\']', query)
    if quoted:
        return quoted[0]

    # Fall back to the most "code-like" word
    words = query.split()
    code_words = [w for w in words if '_' in w or any(c.isupper() for c in w[1:])]
    if code_words:
        return code_words[0]

    # Last resort: use a keyword from the query
    stop_words = {"why", "did", "we", "do", "does", "the", "is", "was", "how", "what", "a", "an", "to"}
    meaningful = [w for w in words if w.lower() not in stop_words]
    return meaningful[0] if meaningful else query
