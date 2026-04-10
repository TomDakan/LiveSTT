"""Unit tests for system_manager.containers module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from docker.errors import NotFound  # type: ignore[import-untyped]
from system_manager.containers import (
    ALL_SERVICES,
    MANAGED_SERVICES,
    disable_service,
    enable_service,
    list_services,
    restart_service,
)


def _mock_container(
    name: str = "stt-provider",
    status: str = "running",
    restart_policy: str = "always",
) -> MagicMock:
    c = MagicMock()
    c.name = name
    c.status = status
    c.attrs = {
        "HostConfig": {
            "RestartPolicy": {"Name": restart_policy},
        }
    }
    return c


def _patch_client() -> Any:
    """Return a patch context for ``_client``."""
    return patch("system_manager.containers._client")


# -------------------------------------------------------------------
# list_services
# -------------------------------------------------------------------


def test_list_services_all_running() -> None:
    containers = {name: _mock_container(name) for name in sorted(ALL_SERVICES)}
    with _patch_client() as mock_fn:
        client = MagicMock()
        mock_fn.return_value = client
        client.containers.get.side_effect = lambda n: containers[n]

        result = list_services()

    assert len(result) == len(ALL_SERVICES)
    names = [r["name"] for r in result]
    assert names == sorted(ALL_SERVICES)
    for entry in result:
        assert entry["status"] == "running"
        assert entry["restart_policy"] == "always"
        expected_managed = entry["name"] in MANAGED_SERVICES
        assert entry["managed"] is expected_managed
    client.close.assert_called_once()


def test_list_services_container_not_found() -> None:
    with _patch_client() as mock_fn:
        client = MagicMock()
        mock_fn.return_value = client
        client.containers.get.side_effect = NotFound("gone")

        result = list_services()

    for entry in result:
        assert entry["status"] == "not_deployed"
        assert entry["restart_policy"] == ""
        assert entry["managed"] is False
    client.close.assert_called_once()


def test_list_services_generic_error() -> None:
    with _patch_client() as mock_fn:
        client = MagicMock()
        mock_fn.return_value = client
        client.containers.get.side_effect = RuntimeError("Docker down")

        result = list_services()

    for entry in result:
        assert entry["status"] == "error"
        assert "error" in entry
        assert "Docker down" in entry["error"]
    client.close.assert_called_once()


# -------------------------------------------------------------------
# _require_managed
# -------------------------------------------------------------------


def test_require_managed_accepts_valid() -> None:
    for name in MANAGED_SERVICES:
        # Should not raise
        from system_manager.containers import _require_managed

        _require_managed(name)


def test_require_managed_rejects_protected() -> None:
    from system_manager.containers import _require_managed

    with pytest.raises(ValueError, match="not manageable"):
        _require_managed("nats")


def test_require_managed_rejects_unknown() -> None:
    from system_manager.containers import _require_managed

    with pytest.raises(ValueError, match="not manageable"):
        _require_managed("foo")


# -------------------------------------------------------------------
# disable_service
# -------------------------------------------------------------------


def test_disable_service_success() -> None:
    container = _mock_container("stt-provider")
    with _patch_client() as mock_fn:
        client = MagicMock()
        mock_fn.return_value = client
        client.containers.get.return_value = container

        result = disable_service("stt-provider")

    assert result["ok"] is True
    assert result["action"] == "disable"
    container.update.assert_called_once_with(restart_policy={"Name": "no"})
    container.stop.assert_called_once_with(timeout=10)
    client.close.assert_called_once()


def test_disable_service_not_found() -> None:
    with _patch_client() as mock_fn:
        client = MagicMock()
        mock_fn.return_value = client
        client.containers.get.side_effect = NotFound("gone")

        result = disable_service("stt-provider")

    assert result["ok"] is False
    assert "not found" in result["error"]
    client.close.assert_called_once()


def test_disable_service_protected_raises() -> None:
    with pytest.raises(ValueError, match="not manageable"):
        disable_service("nats")


# -------------------------------------------------------------------
# enable_service
# -------------------------------------------------------------------


def test_enable_service_success() -> None:
    container = _mock_container("audio-producer")
    with _patch_client() as mock_fn:
        client = MagicMock()
        mock_fn.return_value = client
        client.containers.get.return_value = container

        result = enable_service("audio-producer")

    assert result["ok"] is True
    assert result["action"] == "enable"
    container.update.assert_called_once_with(restart_policy={"Name": "always"})
    container.start.assert_called_once()
    client.close.assert_called_once()


def test_enable_service_not_found() -> None:
    with _patch_client() as mock_fn:
        client = MagicMock()
        mock_fn.return_value = client
        client.containers.get.side_effect = NotFound("gone")

        result = enable_service("audio-producer")

    assert result["ok"] is False
    assert "not found" in result["error"]
    client.close.assert_called_once()


# -------------------------------------------------------------------
# restart_service
# -------------------------------------------------------------------


def test_restart_service_success() -> None:
    container = _mock_container("identity-manager")
    with _patch_client() as mock_fn:
        client = MagicMock()
        mock_fn.return_value = client
        client.containers.get.return_value = container

        result = restart_service("identity-manager")

    assert result["ok"] is True
    assert result["action"] == "restart"
    container.restart.assert_called_once_with(timeout=10)
    client.close.assert_called_once()


def test_restart_service_not_found() -> None:
    with _patch_client() as mock_fn:
        client = MagicMock()
        mock_fn.return_value = client
        client.containers.get.side_effect = NotFound("gone")

        result = restart_service("identity-manager")

    assert result["ok"] is False
    assert "not found" in result["error"]
    client.close.assert_called_once()
