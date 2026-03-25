import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from identity_manager.main import (
    MATCH_WINDOW_S,
    MAX_BUFFER,
    PUBLISH_TIMEOUT_S,
    IdentityManager,
)


def _ts(offset_s: float = 0.0) -> str:
    """Return an ISO 8601 timestamp offset by offset_s seconds from now."""
    return datetime.fromtimestamp(
        datetime.now(UTC).timestamp() + offset_s, tz=UTC
    ).isoformat()


def _transcript(
    text: str = "hello",
    is_final: bool = True,
    source: str = "live",
    ts_offset: float = 0.0,
) -> dict[str, Any]:
    return {
        "text": text,
        "is_final": is_final,
        "confidence": 0.9,
        "timestamp": _ts(ts_offset),
        "source": source,
    }


def _identity(speaker: str = "Alice", ts_offset: float = 0.0) -> dict[str, Any]:
    return {"speaker": speaker, "timestamp": _ts(ts_offset), "confidence": 0.95}


def _make_service() -> IdentityManager:
    service = IdentityManager()
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()
    return service


# --- Unit tests for fusion helpers ---


def test_find_identity_returns_closest_within_window() -> None:
    service = _make_service()
    service._identities = [
        _identity("Alice", ts_offset=-3.0),   # outside window
        _identity("Bob", ts_offset=-0.5),     # inside window, closer
        _identity("Carol", ts_offset=-1.8),   # inside window, further
    ]
    ts = _ts(0.0)
    result = service._find_identity(ts)
    assert result is not None
    assert result["speaker"] == "Bob"


def test_find_identity_returns_none_when_all_outside_window() -> None:
    service = _make_service()
    service._identities = [_identity("Alice", ts_offset=-5.0)]
    assert service._find_identity(_ts(0.0)) is None


def test_find_identity_returns_none_for_bad_timestamp() -> None:
    service = _make_service()
    service._identities = [_identity("Alice")]
    assert service._find_identity(None) is None
    assert service._find_identity("not-a-timestamp") is None


# --- Integration-style tests for the fusion loop ---


@pytest.mark.asyncio
async def test_final_transcript_published_with_matching_identity() -> None:
    """A final transcript with a matching identity gets speaker tag."""
    service = _make_service()
    mock_js = AsyncMock()
    stop_event = asyncio.Event()

    t = _transcript(text="Hello world", is_final=True)
    service._pending = [
        type("P", (), {"data": t, "received_at": asyncio.get_event_loop().time() - PUBLISH_TIMEOUT_S - 1})()
    ]
    service._identities = [_identity("Alice", ts_offset=0.0)]

    task = asyncio.create_task(service._fusion_loop(mock_js, stop_event))
    await asyncio.sleep(0.2)
    stop_event.set()
    await task

    mock_js.publish.assert_called_once()
    subject, raw = mock_js.publish.call_args[0]
    payload = json.loads(raw.decode())
    assert subject == "transcript.final.live"
    assert payload["speaker"] == "Alice"
    assert payload["text"] == "Hello world"


@pytest.mark.asyncio
async def test_final_transcript_published_with_unknown_after_timeout() -> None:
    """A final transcript with no identity gets speaker='Unknown' after timeout."""
    service = _make_service()
    mock_js = AsyncMock()
    stop_event = asyncio.Event()

    t = _transcript(text="Timeout test", is_final=True)
    service._pending = [
        type("P", (), {"data": t, "received_at": asyncio.get_event_loop().time() - PUBLISH_TIMEOUT_S - 1})()
    ]

    task = asyncio.create_task(service._fusion_loop(mock_js, stop_event))
    await asyncio.sleep(0.2)
    stop_event.set()
    await task

    mock_js.publish.assert_called_once()
    payload = json.loads(mock_js.publish.call_args[0][1].decode())
    assert payload["speaker"] == "Unknown"


@pytest.mark.asyncio
async def test_interim_transcript_forwarded_immediately() -> None:
    """Interim transcripts bypass the pending queue and publish right away."""
    service = _make_service()
    mock_js = AsyncMock()
    t = _transcript(text="interim...", is_final=False)
    await service._publish(mock_js, t, speaker=None)

    mock_js.publish.assert_called_once()
    subject, raw = mock_js.publish.call_args[0]
    payload = json.loads(raw.decode())
    assert subject == "transcript.final.live"
    assert payload["speaker"] is None
    assert payload["is_final"] is False


@pytest.mark.asyncio
async def test_backfill_publishes_to_correct_subject() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    t = _transcript(text="backfill text", source="backfill")
    await service._publish(mock_js, t, speaker="Bob")

    subject, _ = mock_js.publish.call_args[0]
    assert subject == "transcript.final.backfill"


@pytest.mark.asyncio
async def test_buffer_capped_at_max_buffer() -> None:
    """Buffers don't grow beyond MAX_BUFFER."""
    service = _make_service()
    mock_js = AsyncMock()
    stop_event = asyncio.Event()

    # Simulate subscriber filling the pending buffer beyond MAX_BUFFER
    for _ in range(MAX_BUFFER + 10):
        service._pending.append(
            type("P", (), {"data": _transcript(), "received_at": 0.0})()
        )

    task = asyncio.create_task(service._fusion_loop(mock_js, stop_event))
    await asyncio.sleep(0.2)
    stop_event.set()
    await task

    # All should have been published (aged out), buffer should be empty
    assert len(service._pending) == 0


@pytest.mark.asyncio
async def test_stream_verification_failure_exits_gracefully() -> None:
    service = _make_service()
    service.nats_manager.ensure_stream = AsyncMock(side_effect=Exception("NATS down"))
    mock_js = AsyncMock()

    with patch.object(service.logger, "critical") as mock_log:
        await service.run_business_logic(mock_js, asyncio.Event())
        mock_log.assert_called_with("Stream verification failed: NATS down")
