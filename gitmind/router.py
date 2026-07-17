"""
Intent Router — Week 3.

Classifies a user query into one of three retrieval intents:
  STRUCTURAL → "where does X happen?" → BM25 index
  RATIONALE  → "why did we do X?"    → Decision Synthesizer
  EPISODE    → "what did we decide?" → Confidence-gated FAISS

Uses a simple regex pattern matcher — no ML needed.
This keeps the router fast (<1ms) and fully interpretable.

TODO (Week 3):
  [ ] Implement route() with the regex pattern tables
  [ ] Add logging to track which intent queries are classified as
  [ ] Write tests covering edge cases
"""

from __future__ import annotations
import re
from gitmind.models import QueryIntent


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

    TODO (Week 3): implement this.
    """
    raise NotImplementedError("Week 3")
