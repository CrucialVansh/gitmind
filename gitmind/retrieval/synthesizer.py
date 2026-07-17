"""
Decision Synthesizer — Week 3.

Reconstructs the "why-arc" for a given function or topic by chaining
all (commit, session) pairs that touched it chronologically.

This is what answers "why did we build it this way?" with a full timeline.

TODO (Week 3):
  [ ] Query DB for all pairs where commit touched the queried function
  [ ] Sort chronologically
  [ ] LLM-extract the rationale from each session chunk
  [ ] Assemble into a DecisionArcEntry list
"""

from __future__ import annotations
from gitmind.models import DecisionArcEntry


class DecisionSynthesizer:
    """Reconstructs decision timelines across sessions. Implemented in Week 3."""

    def synthesize(self, query: str, function_name: str) -> list[DecisionArcEntry]:
        raise NotImplementedError("Week 3")
