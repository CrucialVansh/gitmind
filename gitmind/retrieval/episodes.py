"""
Episode Store — Week 2.

FAISS-backed vector store for session chunks, with a confidence gate.

The confidence gate is THE key differentiator of GitMind.
The paper shows unconstrained episode injection hurts answer quality.
Only inject chunks above settings.episode_gate_threshold.

TODO (Week 2):
  [ ] Embed all session chunks with sentence-transformers
  [ ] Build FAISS flat index
  [ ] Implement search() with the confidence gate
  [ ] Serialize/deserialize to settings.faiss_index_path
"""

from __future__ import annotations
from gitmind.models import RetrievedChunk


class EpisodeStore:
    """Confidence-gated FAISS episode store. Implemented in Week 2."""

    def build(self, chunks: list) -> None:
        raise NotImplementedError("Week 2")

    def search(self, query: str, top_k: int = 10) -> list[RetrievedChunk]:
        """
        Returns chunks sorted by score DESC.
        Sets RetrievedChunk.passed_gate = True only if score >= threshold.
        Callers should filter on passed_gate before injecting into context.
        """
        raise NotImplementedError("Week 2")

    def save(self) -> None:
        raise NotImplementedError("Week 2")

    def load(self) -> None:
        raise NotImplementedError("Week 2")
