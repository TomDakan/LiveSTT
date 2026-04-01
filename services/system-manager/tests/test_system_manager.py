import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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
