"""
Episode Store — Week 2.

FAISS-backed vector store for session chunks, with a confidence gate.

The confidence gate is THE key differentiator of GitMind.
The paper shows unconstrained episode injection hurts answer quality.
Only inject chunks above settings.episode_gate_threshold.
"""

from __future__ import annotations

import logging

import numpy as np

from gitmind.config import settings
from gitmind.models import RetrievedChunk, SessionChunk

logger = logging.getLogger(__name__)


class EpisodeStore:
    """Confidence-gated FAISS episode store."""

    def __init__(self):
        self._index = None
        self._chunks: list[SessionChunk] = []
        self._embedder = None
        self._dimension: int = 0

    def _get_embedder(self):
        """Lazy-load the sentence transformer model."""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(settings.embedding_model)
            logger.info("Loaded embedding model: %s", settings.embedding_model)
        return self._embedder

    def _embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts using the sentence transformer."""
        embedder = self._get_embedder()
        embeddings = embedder.encode(
            texts,
            show_progress_bar=len(texts) > 100,
            normalize_embeddings=True,
            batch_size=64,
        )
        return np.array(embeddings, dtype=np.float32)

    def build(self, chunks: list[SessionChunk]) -> None:
        """
        Embed all session chunks and build a FAISS index.

        Args:
            chunks: List of SessionChunk objects to index.
        """
        import faiss

        if not chunks:
            logger.warning("No chunks to index")
            return

        self._chunks = chunks
        texts = [c.text for c in chunks]

        logger.info("Embedding %d chunks...", len(texts))
        embeddings = self._embed(texts)
        self._dimension = embeddings.shape[1]

        # Build a flat inner product index (for cosine similarity on normalized vectors)
        self._index = faiss.IndexFlatIP(self._dimension)
        self._index.add(embeddings)

        logger.info(
            "Built FAISS index with %d vectors (dim=%d)",
            self._index.ntotal,
            self._dimension,
        )

    def search(self, query: str, top_k: int = 10) -> list[RetrievedChunk]:
        """
        Search for chunks similar to the query.

        Returns chunks sorted by score DESC.
        Sets RetrievedChunk.passed_gate = True only if score >= threshold.
        Callers should filter on passed_gate before injecting into context.
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        query_embedding = self._embed([query])
        scores, indices = self._index.search(query_embedding, min(top_k, self._index.ntotal))

        results: list[RetrievedChunk] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS returns -1 for empty results
                continue

            chunk = self._chunks[idx]
            results.append(
                RetrievedChunk(
                    chunk=chunk,
                    score=float(score),
                    passed_gate=float(score) >= settings.episode_gate_threshold,
                )
            )

        return results

    def save(self) -> None:
        """Serialize the FAISS index and chunk metadata to disk."""
        import faiss
        import json

        if self._index is None:
            logger.warning("No index to save")
            return

        settings.ensure_data_dir()

        # Save FAISS index
        faiss.write_index(self._index, str(settings.faiss_index_path))

        # Save chunk metadata alongside
        meta_path = settings.faiss_index_path.with_suffix(".meta.json")
        chunk_data = [c.model_dump(mode="json") for c in self._chunks]
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"chunks": chunk_data, "dimension": self._dimension}, f)

        logger.info("Saved episode store to %s", settings.faiss_index_path)

    def load(self) -> None:
        """Load the FAISS index and chunk metadata from disk."""
        import faiss
        import json

        if not settings.faiss_index_path.exists():
            logger.warning("No episode store found at %s", settings.faiss_index_path)
            return

        self._index = faiss.read_index(str(settings.faiss_index_path))

        meta_path = settings.faiss_index_path.with_suffix(".meta.json")
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._chunks = [SessionChunk(**c) for c in data["chunks"]]
            self._dimension = data.get("dimension", 0)

        logger.info(
            "Loaded episode store with %d vectors",
            self._index.ntotal if self._index else 0,
        )
