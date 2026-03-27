import contextlib
import logging
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

try:
    import lancedb  # type: ignore[import-not-found]
    import pyarrow as pa  # type: ignore[import-not-found]

    LANCEDB_AVAILABLE = True
except ImportError:
    lancedb = None  # type: ignore[assignment]
    pa = None  # type: ignore[assignment]
    LANCEDB_AVAILABLE = False

from .interfaces import VoiceprintStore

logger = logging.getLogger(__name__)

_TABLE_NAME = "voiceprints"
_EMBEDDING_DIM = 256
_SCHEMA = None  # built lazily when lancedb is available


def _schema() -> "pa.Schema":
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), _EMBEDDING_DIM)),
            pa.field("enrolled_at", pa.string()),
        ]
    )


class StubVoiceprintStore(VoiceprintStore):
    """No-op store — never matches; enroll/delete are no-ops."""

    def enroll(self, name: str, embedding: np.ndarray) -> None:
        logger.warning(f"StubVoiceprintStore: enroll('{name}') ignored.")

    def identify(
        self, embedding: np.ndarray, threshold: float = 0.25
    ) -> tuple[str, float] | None:
        return None

    def delete(self, name: str) -> None:
        logger.warning(f"StubVoiceprintStore: delete('{name}') ignored.")


class LanceDBVoiceprintStore(VoiceprintStore):
    """
    Voiceprint store backed by LanceDB.

    Embeddings are 256-dim float32 vectors (WeSpeaker ResNet34, L2-normalised).
    Identification uses cosine distance; threshold is maximum accepted distance
    (default 0.25 ≈ cosine similarity > 0.75).
    """

    def __init__(self, db_path: str = "/data/lancedb") -> None:
        if not LANCEDB_AVAILABLE:
            raise RuntimeError(
                "lancedb and pyarrow are required for LanceDBVoiceprintStore. "
                "Install them or use StubVoiceprintStore."
            )
        Path(db_path).mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(db_path)
        self._table = self._open_or_create_table()
        logger.info(f"LanceDB voiceprint store ready at {db_path}")

    def _open_or_create_table(self) -> "lancedb.table.Table":
        if _TABLE_NAME in self._db.table_names():
            return self._db.open_table(_TABLE_NAME)
        return self._db.create_table(_TABLE_NAME, schema=_schema())

    def enroll(self, name: str, embedding: np.ndarray) -> None:
        # Remove existing entry before inserting (upsert)
        with contextlib.suppress(Exception):
            self._table.delete(f"id = '{name}'")
        self._table.add(
            [
                {
                    "id": name,
                    "vector": embedding.astype(np.float32).tolist(),
                    "enrolled_at": datetime.now(UTC).isoformat(),
                }
            ]
        )
        logger.info(f"Enrolled voiceprint for '{name}'")

    def identify(
        self, embedding: np.ndarray, threshold: float = 0.25
    ) -> tuple[str, float] | None:
        try:
            results = (
                self._table.search(embedding.astype(np.float32))
                .metric("cosine")
                .limit(1)
                .to_list()
            )
        except Exception as e:
            logger.error(f"LanceDB search failed: {e}")
            return None

        if not results:
            return None

        distance = float(results[0].get("_distance", 1.0))
        if distance > threshold:
            return None

        return (results[0]["id"], round(1.0 - distance, 4))

    def delete(self, name: str) -> None:
        self._table.delete(f"id = '{name}'")
        # Compact to physically remove the row (crypto-shred support)
        with contextlib.suppress(Exception):
            self._table.compact_files()
        logger.info(f"Deleted voiceprint for '{name}'")
