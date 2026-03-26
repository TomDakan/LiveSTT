import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from data_sweeper.main import MONITORED_STREAMS, DataSweeper


def _make_service() -> DataSweeper:
    service = DataSweeper()
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()
    return service


def _make_stream_info(messages: int = 10, bytes_: int = 4096, consumers: int = 1) -> MagicMock:
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

    task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))
    await asyncio.sleep(0.05)
    stop_event.set()
    await task

    mock_js.stream_info.assert_called()
