import asyncio
import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from system_manager.main import MONITORED_STREAMS, SystemManager


def _make_service() -> SystemManager:
    service = SystemManager()
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()
    return service


def _make_stream_info(
    messages: int = 10, bytes_: int = 4096, consumers: int = 1
) -> MagicMock:
    info = MagicMock()
    info.state.messages = messages
    info.state.bytes = bytes_
    info.state.consumer_count = consumers
    return info


@pytest.mark.asyncio
async def test_report_stats_logs_all_streams() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.stream_info = AsyncMock(return_value=_make_stream_info())

    with patch.object(service.logger, "info") as mock_info:
        await service._report_stream_stats(mock_js)

    assert mock_js.stream_info.call_count == len(MONITORED_STREAMS)
    logged = [call.args[0] for call in mock_info.call_args_list]
    for stream_name in MONITORED_STREAMS:
        assert any(stream_name in msg for msg in logged)


@pytest.mark.asyncio
async def test_report_stats_logs_correct_values() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.stream_info = AsyncMock(
        return_value=_make_stream_info(messages=42, bytes_=2048, consumers=3)
    )

    with patch.object(service.logger, "info") as mock_info:
        await service._report_stream_stats(mock_js)

    logged = " ".join(call.args[0] for call in mock_info.call_args_list)
    assert "42" in logged
    assert "2.0" in logged  # 2048 / 1024 = 2.0 KB
    assert "3" in logged


@pytest.mark.asyncio
async def test_unavailable_stream_logs_warning() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.stream_info = AsyncMock(side_effect=Exception("stream not found"))

    with patch.object(service.logger, "warning") as mock_warn:
        await service._report_stream_stats(mock_js)

    assert mock_warn.call_count == len(MONITORED_STREAMS)
    assert all("unavailable" in call.args[0] for call in mock_warn.call_args_list)


@pytest.mark.asyncio
async def test_run_business_logic_stops_on_event() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.stream_info = AsyncMock(return_value=_make_stream_info())
    stop_event = asyncio.Event()

    # Ensure the report interval condition triggers on first iteration
    # (loop.time() may be < REPORT_INTERVAL_S on fresh CI runners)
    service._last_report = -1800.0
    with patch.object(service, "_check_schedules", new_callable=AsyncMock):
        task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))
        await asyncio.sleep(0.05)
        stop_event.set()
        await task

    mock_js.stream_info.assert_called()


@pytest.mark.asyncio
async def test_fire_start_publishes_command() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.publish = AsyncMock()

    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime(2026, 3, 30, 10, 30, tzinfo=ZoneInfo("UTC"))
    sched = {
        "id": "abc123",
        "label_template": "Sunday Morning — {date}",
        "stop_policy": "soft",
    }

    await service._fire_start(mock_js, sched, now)
    mock_js.publish.assert_called_once()
    call_args = mock_js.publish.call_args
    assert call_args[0][0] == "session.control"
    import json

    payload = json.loads(call_args[0][1])
    assert payload["command"] == "start"
    assert payload["scheduled"] is True
    assert "March 30" in payload["label"]


@pytest.mark.asyncio
async def test_fire_stop_soft_skips() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.publish = AsyncMock()

    sched = {"id": "abc123", "stop_policy": "soft"}
    await service._fire_stop(mock_js, sched)

    mock_js.publish.assert_not_called()


@pytest.mark.asyncio
async def test_fire_stop_hard_publishes() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.publish = AsyncMock()

    sched = {"id": "abc123", "stop_policy": "hard"}
    await service._fire_stop(mock_js, sched)

    mock_js.publish.assert_called_once()
    import json

    payload = json.loads(mock_js.publish.call_args[0][1])
    assert payload["command"] == "stop"


# ---------------------------------------------------------------------------
# _within_window — parametrized boundary tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current, target, expected",
    [
        # Exact match → inside window
        ("09:00", "09:00", True),
        # 1 minute after → still inside (window=2)
        ("09:01", "09:00", True),
        # 2 minutes after → outside [target, target+2)
        ("09:02", "09:00", False),
        # 1 minute before → negative diff → outside
        ("08:59", "09:00", False),
        # Far apart
        ("12:00", "09:00", False),
        # Late evening
        ("23:59", "23:58", True),
        # Midnight target, current at 00:00
        ("00:00", "00:00", True),
        ("00:01", "00:00", True),
        ("00:02", "00:00", False),
        # No midnight wrap: 23:59 is NOT within window of 00:00
        # (diff = 23*60+59 - 0 = 1439, not in [0,2))
        ("23:59", "00:00", False),
    ],
    ids=[
        "exact_match",
        "one_min_after",
        "two_min_after_excluded",
        "one_min_before",
        "far_apart",
        "late_evening",
        "midnight_exact",
        "midnight_plus_one",
        "midnight_plus_two",
        "no_midnight_wrap",
    ],
)
def test_within_window(current: str, target: str, expected: bool) -> None:
    assert SystemManager._within_window(current, target) is expected


def test_within_window_custom_window() -> None:
    """Wider window (5 min) allows more slack."""
    assert SystemManager._within_window("09:04", "09:00", window_minutes=5) is True
    assert SystemManager._within_window("09:05", "09:00", window_minutes=5) is False


# ---------------------------------------------------------------------------
# _eval_schedule — schedule evaluation logic
# ---------------------------------------------------------------------------


def _base_schedule(
    *,
    sched_id: str = "sched-1",
    enabled: bool = True,
    days: list[int] | None = None,
    start_time: str = "09:00",
    stop_time: str = "10:00",
    stop_policy: str = "hard",
) -> dict[str, Any]:
    return {
        "id": sched_id,
        "enabled": enabled,
        "day_of_week": days if days is not None else [0],  # Sunday
        "start_time": start_time,
        "stop_time": stop_time,
        "stop_policy": stop_policy,
        "label_template": "Service — {date}",
    }


@pytest.mark.asyncio
async def test_eval_schedule_disabled_skips() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.publish = AsyncMock()

    sched = _base_schedule(enabled=False)
    now = datetime(2026, 3, 29, 9, 0, tzinfo=ZoneInfo("UTC"))  # Sunday

    await service._eval_schedule(mock_js, sched, now, 0, "09:00")
    mock_js.publish.assert_not_called()


@pytest.mark.asyncio
async def test_eval_schedule_wrong_day_skips() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.publish = AsyncMock()

    sched = _base_schedule(days=[0])  # Sunday only
    now = datetime(2026, 3, 30, 9, 0, tzinfo=ZoneInfo("UTC"))  # Monday

    await service._eval_schedule(mock_js, sched, now, 1, "09:00")  # dow=1=Mon
    mock_js.publish.assert_not_called()


@pytest.mark.asyncio
async def test_eval_schedule_fires_start_in_window() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.publish = AsyncMock()

    sched = _base_schedule(days=[0], start_time="09:00", stop_time="10:00")
    now = datetime(2026, 3, 29, 9, 0, tzinfo=ZoneInfo("UTC"))

    await service._eval_schedule(mock_js, sched, now, 0, "09:00")

    mock_js.publish.assert_called_once()
    payload = json.loads(mock_js.publish.call_args[0][1])
    assert payload["command"] == "start"


@pytest.mark.asyncio
async def test_eval_schedule_fires_stop_in_window() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.publish = AsyncMock()

    sched = _base_schedule(
        days=[0], start_time="09:00", stop_time="10:00", stop_policy="hard"
    )
    now = datetime(2026, 3, 29, 10, 0, tzinfo=ZoneInfo("UTC"))

    await service._eval_schedule(mock_js, sched, now, 0, "10:00")

    mock_js.publish.assert_called_once()
    payload = json.loads(mock_js.publish.call_args[0][1])
    assert payload["command"] == "stop"


@pytest.mark.asyncio
async def test_eval_schedule_dedup_prevents_double_fire() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.publish = AsyncMock()

    sched = _base_schedule(days=[0], start_time="09:00", stop_time="10:00")
    now = datetime(2026, 3, 29, 9, 0, tzinfo=ZoneInfo("UTC"))

    # First eval fires
    await service._eval_schedule(mock_js, sched, now, 0, "09:00")
    assert mock_js.publish.call_count == 1

    # Second eval same day — dedup blocks it
    mock_js.publish.reset_mock()
    await service._eval_schedule(mock_js, sched, now, 0, "09:01")
    mock_js.publish.assert_not_called()


@pytest.mark.asyncio
async def test_eval_schedule_both_start_and_stop_same_time() -> None:
    """If start and stop windows overlap (same time), both fire."""
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.publish = AsyncMock()

    sched = _base_schedule(
        days=[0],
        start_time="09:00",
        stop_time="09:00",
        stop_policy="hard",
    )
    now = datetime(2026, 3, 29, 9, 0, tzinfo=ZoneInfo("UTC"))

    await service._eval_schedule(mock_js, sched, now, 0, "09:00")
    assert mock_js.publish.call_count == 2
