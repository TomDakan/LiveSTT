import asyncio
import json
import struct
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from identifier.embedder import StubEmbedder
from identifier.interfaces import Embedder, VoiceprintStore
from identifier.main import _WINDOW_SAMPLES, IdentifierService, _AudioBuffer
from identifier.store import StubVoiceprintStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FixedEmbedder(Embedder):
    """Always returns the same normalised embedding."""

    def __init__(self, seed: int = 0) -> None:
        v = np.random.default_rng(seed).standard_normal(256).astype(np.float32)
        self._vec = v / np.linalg.norm(v)

    def embed(self, audio_pcm: bytes) -> np.ndarray:
        return self._vec.copy()


class _MatchingStore(VoiceprintStore):
    """Always returns a match for the given speaker."""

    def __init__(self, speaker: str = "Alice", confidence: float = 0.9) -> None:
        self._speaker = speaker
        self._confidence = confidence

    def enroll(self, name: str, embedding: np.ndarray) -> None:
        pass

    def identify(
        self, embedding: np.ndarray, threshold: float = 0.25
    ) -> tuple[str, float]:
        return (self._speaker, self._confidence)

    def delete(self, name: str) -> None:
        pass


def _chunk(n_samples: int = 1536) -> bytes:
    return struct.pack(f"<{n_samples}h", *([100] * n_samples))


def _make_service(
    embedder: Embedder | None = None,
    store: VoiceprintStore | None = None,
) -> IdentifierService:
    svc = IdentifierService(
        embedder=embedder or StubEmbedder(),
        store=store or StubVoiceprintStore(),
    )
    svc.nats_manager = MagicMock()
    svc.nats_manager.ensure_stream = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# _AudioBuffer unit tests
# ---------------------------------------------------------------------------


def test_buffer_not_ready_below_window() -> None:
    buf = _AudioBuffer()
    buf.add(_chunk(1000))
    assert not buf.ready()


def test_buffer_ready_at_window() -> None:
    buf = _AudioBuffer()
    # Add exactly WINDOW_SAMPLES worth of int16 data
    buf.add(b"\x00\x01" * _WINDOW_SAMPLES)
    assert buf.ready()


def test_buffer_consume_clears_state() -> None:
    buf = _AudioBuffer()
    buf.add(_chunk(1536))
    buf.consume()
    assert buf.sample_count == 0
    assert buf.chunks == []


# ---------------------------------------------------------------------------
# Pipeline integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_publish_when_stub_embedder() -> None:
    """StubEmbedder returns None → nothing published."""
    svc = _make_service(embedder=StubEmbedder(), store=_MatchingStore())
    mock_js = AsyncMock()

    await svc._identify_and_publish(mock_js, _chunk(_WINDOW_SAMPLES), "sess1", "live")

    mock_js.publish.assert_not_called()


@pytest.mark.asyncio
async def test_no_publish_when_no_store_match() -> None:
    """Embedding found but no voiceprint match → nothing published."""
    svc = _make_service(embedder=_FixedEmbedder(), store=StubVoiceprintStore())
    mock_js = AsyncMock()

    await svc._identify_and_publish(mock_js, _chunk(_WINDOW_SAMPLES), "sess1", "live")

    mock_js.publish.assert_not_called()


@pytest.mark.asyncio
async def test_publishes_identity_event_on_match() -> None:
    """Known speaker → identity event published to correct subject."""
    svc = _make_service(
        embedder=_FixedEmbedder(),
        store=_MatchingStore(speaker="Alice", confidence=0.9),
    )
    mock_js = AsyncMock()

    await svc._identify_and_publish(mock_js, _chunk(_WINDOW_SAMPLES), "sess1", "live")

    mock_js.publish.assert_called_once()
    subject, raw = mock_js.publish.call_args[0]
    payload = json.loads(raw.decode())
    assert subject == "transcript.identity.live"
    assert payload["speaker"] == "Alice"
    assert payload["confidence"] == pytest.approx(0.9)
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_publishes_to_backfill_subject() -> None:
    svc = _make_service(
        embedder=_FixedEmbedder(),
        store=_MatchingStore(speaker="Bob"),
    )
    mock_js = AsyncMock()

    await svc._identify_and_publish(mock_js, _chunk(_WINDOW_SAMPLES), "sess1", "backfill")

    subject, _ = mock_js.publish.call_args[0]
    assert subject == "transcript.identity.backfill"


@pytest.mark.asyncio
async def test_worker_buffers_chunks_until_window_full() -> None:
    """Worker should not publish until a full window of audio is buffered."""
    svc = _make_service(
        embedder=_FixedEmbedder(),
        store=_MatchingStore(speaker="Alice"),
    )
    mock_js = AsyncMock()
    stop_event = asyncio.Event()

    # Build enough msgs to fill one window (ceil(WINDOW_SAMPLES / 1536) chunks)
    import math

    n_chunks = math.ceil(_WINDOW_SAMPLES / 1536)
    chunk_bytes = _chunk(1536)

    msgs = []
    for _ in range(n_chunks):
        m = MagicMock()
        m.subject = "audio.live.session1"
        m.data = chunk_bytes
        m.ack = AsyncMock()
        msgs.append(m)

    call_count = 0

    async def fake_fetch(n: int, timeout: float) -> list:
        nonlocal call_count
        if call_count < len(msgs):
            msg = msgs[call_count]
            call_count += 1
            return [msg]
        stop_event.set()
        raise TimeoutError

    mock_sub = MagicMock()
    mock_sub.fetch = fake_fetch
    mock_js.pull_subscribe = AsyncMock(return_value=mock_sub)

    await svc._worker(mock_js, stop_event, "audio.live.>", "live")

    mock_js.publish.assert_called_once()
