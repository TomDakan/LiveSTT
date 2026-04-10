"""End-to-end integration tests for the audio → transcript pipeline.

Requires a running NATS server (started by ``scripts/run_integration_tests.py``).
Uses ``MockTranscriber`` so **no Deepgram key is needed**.

Flow tested:
    publish audio chunks → NATS AUDIO_STREAM →
    stt-provider (MockTranscriber) → NATS TRANSCRIPTION_STREAM
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from messaging.nats import NatsJSManager
from messaging.streams import (
    AUDIO_STREAM_CONFIG,
    SUBJECT_PREFIX_AUDIO_BACKFILL,
    SUBJECT_PREFIX_AUDIO_LIVE,
    TRANSCRIPTION_STREAM_CONFIG,
)
from stt_provider.interfaces import Transcriber, TranscriptionEvent
from stt_provider.main import STTProviderService

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
SESSION_ID = "20260409-1000"
AUDIO_CHUNK = b"\x00" * 3072  # 1536 samples x 2 bytes (16-bit PCM)


# ---------------------------------------------------------------------------
# Inline MockTranscriber (test dirs have no __init__.py so we can't import)
# ---------------------------------------------------------------------------


class _MockTranscriber(Transcriber):
    """Minimal mock: emits one final event per 5 audio chunks."""

    def __init__(self) -> None:
        self.connected = False
        self._queue: asyncio.Queue[TranscriptionEvent | None] = asyncio.Queue()
        self._chunk_count = 0

    async def connect(self, **kwargs: Any) -> None:
        self.connected = True

    async def send_audio(self, audio: bytes) -> None:
        self._chunk_count += 1
        if self._chunk_count % 5 == 0:
            await self._queue.put(
                TranscriptionEvent(
                    text=f"sentence {self._chunk_count // 5}",
                    is_final=True,
                    confidence=0.95,
                )
            )

    async def finalize(self) -> None:
        await self._queue.put(TranscriptionEvent(text="", is_final=True, confidence=0.0))

    async def finish(self) -> None:
        await self._queue.put(None)

    async def get_events(self) -> AsyncIterator[TranscriptionEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _publish_audio_session(
    js: Any,
    *,
    subject_prefix: str,
    num_chunks: int = 10,
) -> None:
    """Publish ``num_chunks`` audio messages then an EOS marker."""
    subject = f"{subject_prefix}.{SESSION_ID}"
    for _ in range(num_chunks):
        await js.publish(subject, AUDIO_CHUNK)
    await js.publish(
        subject,
        b"",
        headers={"LiveSTT-EOS": "true"},
    )


async def _collect_transcripts(
    sub: Any,
    timeout_s: float = 15.0,
    min_count: int = 1,
) -> list[dict[str, Any]]:
    """Drain a pre-created subscription for final transcripts."""
    results: list[dict[str, Any]] = []
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            msg = await sub.next_msg(timeout=min(remaining, 1.0))
            data = json.loads(msg.data.decode())
            if data.get("is_final"):
                results.append(data)
                if len(results) >= min_count:
                    break
        except TimeoutError:
            continue
    await sub.unsubscribe()
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_to_transcript_via_nats() -> None:
    """Full pipeline: audio chunks → NATS → stt-provider → transcript on NATS."""
    # 1. Setup NATS streams
    mgr = NatsJSManager()
    nc, js = await mgr.connect(NATS_URL)

    await mgr.ensure_stream(**AUDIO_STREAM_CONFIG)
    await mgr.ensure_stream(**TRANSCRIPTION_STREAM_CONFIG)

    # Purge stale data from prior test runs
    with contextlib.suppress(Exception):
        await js.purge_stream("AUDIO_STREAM")
    with contextlib.suppress(Exception):
        await js.purge_stream("TRANSCRIPTION_STREAM")
    for durable in ("stt_backfill", "stt_live"):
        with contextlib.suppress(Exception):
            await js.delete_consumer("AUDIO_STREAM", durable)

    # 2. Subscribe to transcripts BEFORE publishing audio (avoids race)
    transcript_sub = await nc.subscribe("transcript.raw.>")

    # 3. Start stt-provider with mock transcriber
    service = STTProviderService(transcriber_factory=_MockTranscriber)
    service.nats_url = NATS_URL
    svc_task = asyncio.create_task(service.start())

    # Give service time to connect and subscribe
    await asyncio.sleep(2.0)

    # 4. Publish backfill audio (10 chunks -> 2 final transcripts)
    await _publish_audio_session(
        js, subject_prefix=SUBJECT_PREFIX_AUDIO_BACKFILL, num_chunks=10
    )

    # Small delay then publish live audio
    await asyncio.sleep(0.5)
    await _publish_audio_session(
        js, subject_prefix=SUBJECT_PREFIX_AUDIO_LIVE, num_chunks=10
    )

    # 5. Collect transcripts
    transcripts = await _collect_transcripts(transcript_sub, timeout_s=15.0, min_count=2)

    # 6. Stop service
    service.stop_event.set()
    try:
        await asyncio.wait_for(svc_task, timeout=5.0)
    except (TimeoutError, asyncio.CancelledError):
        svc_task.cancel()

    await mgr.close()

    # 7. Assertions
    assert len(transcripts) >= 2, (
        f"Expected at least 2 final transcripts, got {len(transcripts)}"
    )
    for t in transcripts:
        assert "text" in t
        assert t["is_final"] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_late_consumer_catches_up() -> None:
    """Publish audio first, then start stt-provider — JetStream replays."""
    # 1. Setup NATS streams
    mgr = NatsJSManager()
    nc, js = await mgr.connect(NATS_URL)

    await mgr.ensure_stream(**AUDIO_STREAM_CONFIG)
    await mgr.ensure_stream(**TRANSCRIPTION_STREAM_CONFIG)

    # Purge any leftover messages from previous tests
    try:
        await js.purge_stream("AUDIO_STREAM")
        await js.purge_stream("TRANSCRIPTION_STREAM")
    except Exception:
        pass

    # Delete stale durable consumers so the new service starts fresh
    for durable in ("stt_backfill", "stt_live"):
        with contextlib.suppress(Exception):
            await js.delete_consumer("AUDIO_STREAM", durable)

    # 2. Subscribe to transcripts BEFORE publishing (avoids race)
    transcript_sub = await nc.subscribe("transcript.raw.>")

    # 3. Publish audio BEFORE the consumer exists
    await _publish_audio_session(
        js, subject_prefix=SUBJECT_PREFIX_AUDIO_BACKFILL, num_chunks=10
    )
    await _publish_audio_session(
        js, subject_prefix=SUBJECT_PREFIX_AUDIO_LIVE, num_chunks=10
    )

    # 4. Now start stt-provider — it should catch up via JetStream replay
    service = STTProviderService(transcriber_factory=_MockTranscriber)
    service.nats_url = NATS_URL
    svc_task = asyncio.create_task(service.start())

    # 5. Collect transcripts
    transcripts = await _collect_transcripts(transcript_sub, timeout_s=15.0, min_count=2)

    # 6. Cleanup
    service.stop_event.set()
    try:
        await asyncio.wait_for(svc_task, timeout=5.0)
    except (TimeoutError, asyncio.CancelledError):
        svc_task.cancel()

    await mgr.close()

    # 7. Verify catch-up worked
    assert len(transcripts) >= 2, (
        f"Late consumer should catch up; got {len(transcripts)} transcripts"
    )
