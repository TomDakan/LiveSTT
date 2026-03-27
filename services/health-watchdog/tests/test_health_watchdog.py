import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from health_watchdog.main import (
    HEALTH_BUCKET,
    MONITORED_SERVICES,
    HealthWatchdog,
)


def _make_service() -> HealthWatchdog:
    service = HealthWatchdog()
    service.nats_manager = MagicMock()
    service.nats_manager.ensure_stream = AsyncMock()
    return service


def _make_js(alive_keys: list[str]) -> AsyncMock:
    mock_kv = AsyncMock()
    mock_kv.keys = AsyncMock(return_value=alive_keys)
    mock_js = AsyncMock()
    mock_js.key_value = AsyncMock(return_value=mock_kv)
    return mock_js


@pytest.mark.asyncio
async def test_all_services_healthy_no_warnings() -> None:
    service = _make_service()
    mock_js = _make_js(alive_keys=list(MONITORED_SERVICES))

    with patch.object(service.logger, "warning") as mock_warn:
        await service._check_services(mock_js)
        mock_warn.assert_not_called()

    mock_js.key_value.assert_called_once_with(HEALTH_BUCKET)


@pytest.mark.asyncio
async def test_missing_service_logs_warning() -> None:
    service = _make_service()
    # All monitored services except the first one
    alive = list(MONITORED_SERVICES[1:])
    mock_js = _make_js(alive_keys=alive)
    missing = MONITORED_SERVICES[0]

    with patch.object(service.logger, "warning") as mock_warn:
        await service._check_services(mock_js)
        messages = [call.args[0] for call in mock_warn.call_args_list]
        assert any(missing in m and "DOWN" in m for m in messages)


@pytest.mark.asyncio
async def test_kv_unavailable_logs_warning() -> None:
    service = _make_service()
    mock_js = AsyncMock()
    mock_js.key_value = AsyncMock(side_effect=Exception("bucket not found"))

    with patch.object(service.logger, "warning") as mock_warn:
        await service._check_services(mock_js)
        mock_warn.assert_called_once()
        assert HEALTH_BUCKET in mock_warn.call_args[0][0]


@pytest.mark.asyncio
async def test_unexpected_service_logs_info() -> None:
    service = _make_service()
    extra = "mystery-service"
    mock_js = _make_js(alive_keys=[*MONITORED_SERVICES, extra])

    with patch.object(service.logger, "info") as mock_info:
        await service._check_services(mock_js)
        messages = [call.args[0] for call in mock_info.call_args_list]
        assert any(extra in m for m in messages)


@pytest.mark.asyncio
async def test_run_business_logic_stops_on_event() -> None:
    service = _make_service()
    mock_js = _make_js(alive_keys=list(MONITORED_SERVICES))
    stop_event = asyncio.Event()

    task = asyncio.create_task(service.run_business_logic(mock_js, stop_event))
    await asyncio.sleep(0.05)
    stop_event.set()
    await task

    # Should have called _check_services at least once
    mock_js.key_value.assert_called()
