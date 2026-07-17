"""
Configuration management for GitMind.

Loads settings from environment variables (.env file) and provides
a single `settings` object used throughout the app.
"""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    All GitMind runtime settings.
    Values are loaded from environment variables or .env file.
    """

    # ── LLM ──────────────────────────────────────────────────────────────────
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # ── Storage ───────────────────────────────────────────────────────────────
    data_dir: Path = Field(
        default=Path.home() / ".gitmind",
        alias="GITMIND_DATA_DIR",
    )

    # ── Retrieval ─────────────────────────────────────────────────────────────
    episode_gate_threshold: float = Field(
        default=0.72,
        alias="GITMIND_EPISODE_GATE_THRESHOLD",
        description="Similarity threshold below which episode chunks are dropped",
    )
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="GITMIND_EMBEDDING_MODEL",
    )

    # ── Linking ───────────────────────────────────────────────────────────────
    link_time_window_seconds: int = Field(
        default=7200,  # ±2 hours
        alias="GITMIND_LINK_TIME_WINDOW_SECONDS",
    )

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", alias="GITMIND_LOG_LEVEL")

    model_config = {"env_file": ".env", "populate_by_name": True}

    @property
    def db_path(self) -> Path:
        """Path to the SQLite database file."""
        return self.data_dir / "store.db"

    @property
    def faiss_index_path(self) -> Path:
        """Path to the FAISS index file."""
        return self.data_dir / "episodes.faiss"

    @property
    def bm25_index_path(self) -> Path:
        """Path to the serialised BM25 structural index."""
        return self.data_dir / "structural.pkl"

    def ensure_data_dir(self) -> None:
        """Create the data directory if it doesn't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)


# Singleton — import this everywhere
settings = Settings()
