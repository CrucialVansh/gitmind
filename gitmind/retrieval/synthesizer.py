"""
Decision Synthesizer — Week 3.

Reconstructs the "why-arc" for a given function or topic by chaining
all (commit, session) pairs that touched it chronologically.

This is what answers "why did we build it this way?" with a full timeline.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from gitmind.db import GitMindDB
from gitmind.models import DecisionArcEntry

logger = logging.getLogger(__name__)


class DecisionSynthesizer:
    """Reconstructs decision timelines across sessions."""

    def __init__(self, db: GitMindDB | None = None):
        self._db = db or GitMindDB()

    def synthesize(self, _query: str, function_name: str) -> list[DecisionArcEntry]:
        """
        Build a chronological decision arc for a function.

        Steps:
            1. Query DB for all commit-session pairs touching the function.
            2. Sort chronologically.
            3. Extract rationale summaries from the session chunks.
            4. Assemble into DecisionArcEntry list.

        Args:
            query: The user's original query (for context).
            function_name: The function/symbol to trace.

        Returns:
            Chronologically ordered list of DecisionArcEntry objects.
        """
        # Get all pairs touching this function
        pair_records = self._db.get_pairs_for_function(function_name)

        if not pair_records:
            logger.info("No pairs found for function '%s'", function_name)
            return []

        entries: list[DecisionArcEntry] = []

        for record in pair_records:
            commit_hash = record["commit_hash"]
            session_id = record["session_id"]
            chunk_ids = json.loads(record.get("chunk_ids", "[]"))

            # Get the session to access chunks
            session = self._db.get_session(session_id)
            if not session:
                continue

            # Find the relevant chunks
            relevant_text_parts: list[str] = []
            for chunk in session.chunks:
                if chunk.chunk_id in chunk_ids:
                    relevant_text_parts.append(chunk.text)

            # If no specific chunks found, use the session's transcript excerpt
            if not relevant_text_parts and session.raw_transcript:
                # Take first 500 chars as a summary
                relevant_text_parts.append(session.raw_transcript[:500])

            rationale_summary = _extract_rationale(
                "\n".join(relevant_text_parts),
                function_name,
            )

            commit_timestamp = record.get("commit_timestamp")
            if commit_timestamp:
                date = datetime.fromtimestamp(commit_timestamp, tz=timezone.utc)
            else:
                date = datetime.now(tz=timezone.utc)

            entries.append(
                DecisionArcEntry(
                    date=date,
                    commit_hash=commit_hash,
                    rationale_summary=rationale_summary,
                    source_chunk_id=chunk_ids[0] if chunk_ids else f"{session_id}::summary",
                )
            )

        # Sort chronologically (oldest first for the timeline)
        entries.sort(key=lambda e: e.date)

        logger.info(
            "Synthesized decision arc for '%s': %d entries",
            function_name,
            len(entries),
        )

        return entries


def _extract_rationale(text: str, function_name: str) -> str:
    """
    Extract a concise rationale summary from session chunk text.

    Uses simple heuristics — can be enhanced with LLM in a future version.
    """
    if not text:
        return "No rationale found."

    # Try to find sentences mentioning the function
    import re
    sentences = re.split(r'[.!?]+', text)
    relevant = [
        s.strip()
        for s in sentences
        if function_name.lower() in s.lower() or any(
            keyword in s.lower()
            for keyword in ["because", "reason", "decided", "changed", "switched", "why"]
        )
    ]

    if relevant:
        # Return the most relevant sentences (up to 3)
        summary = ". ".join(relevant[:3])
        if len(summary) > 500:
            summary = summary[:497] + "..."
        return summary

    # Fallback: return a truncated version of the text
    summary = text.strip()
    if len(summary) > 300:
        summary = summary[:297] + "..."
    return summary
