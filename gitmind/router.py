"""
Intent Router — Week 3.

Classifies a user query into one of three retrieval intents:
  STRUCTURAL → "where does X happen?" → BM25 index
  RATIONALE  → "why did we do X?"    → Decision Synthesizer
  EPISODE    → "what did we decide?" → Confidence-gated FAISS

Uses a simple regex pattern matcher — no ML needed.
This keeps the router fast (<1ms) and fully interpretable.
"""

from __future__ import annotations

import logging
import re

from gitmind.models import QueryIntent

logger = logging.getLogger(__name__)

# Pattern tables — order matters (first match wins)
_PATTERNS: list[tuple[QueryIntent, list[str]]] = [
    (QueryIntent.RATIONALE, [
        r"why (did|do|does|didn't|don't)",
        r"what (was|is) the (reason|rationale|decision|motivation)",
        r"why (not|changed|switched|moved|removed|added)",
        r"what (made|caused) (you|us|the team)",
        r"how did (we|you) (decide|choose|end up)",
    ]),
    (QueryIntent.STRUCTURAL, [
        r"where (is|does|are|do)",
        r"which (file|function|module|class|method)",
        r"how (is|does) .+ (called|used|imported|referenced)",
        r"what (calls|uses|imports|depends on)",
        r"find (the|all) .+ (function|method|class|module)",
    ]),
    # EPISODE is the default — matches broad "what" questions
    (QueryIntent.EPISODE, [
        r"what (did|does|happened|changed)",
        r"how (to|do I|should I|can I)",
        r"tell me about",
        r"explain",
    ]),
]


def route(query: str) -> QueryIntent:
    """
    Classify a user query into a QueryIntent.

    Args:
        query: The raw user query string.

    Returns:
        QueryIntent enum value.
    """
    query_lower = query.lower().strip()

    for intent, patterns in _PATTERNS:
        for pattern in patterns:
            if re.search(pattern, query_lower):
                logger.debug("Routed query to %s (matched: %s)", intent.value, pattern)
                return intent

    # Default to EPISODE for unmatched queries
    logger.debug("No pattern matched — defaulting to EPISODE")
    return QueryIntent.EPISODE
