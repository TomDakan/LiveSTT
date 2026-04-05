"""Docker container management for service enable/disable/restart.

Only containers in MANAGED_SERVICES can be controlled.  Protected
services (nats, api-gateway, system-manager) are excluded to prevent
self-inflicted outages.
"""

from __future__ import annotations

import logging
from typing import Any

import docker  # type: ignore[import-untyped]
from docker.errors import NotFound  # type: ignore[import-untyped]

logger = logging.getLogger("system-manager")

# Container names that the admin UI can toggle.
MANAGED_SERVICES: set[str] = {
    "audio-producer",
    "stt-provider",
    "identity-manager",
    "health-watchdog",
}

# All known container names (managed + protected) for listing.
ALL_SERVICES: set[str] = MANAGED_SERVICES | {
    "nats",
    "api-gateway",
    "system-manager",
}


def _client() -> docker.DockerClient:
    return docker.from_env()


def list_services() -> list[dict[str, Any]]:
    """Return status of all known containers."""
    client = _client()
    result: list[dict[str, Any]] = []
    for name in sorted(ALL_SERVICES):
        try:
            c = client.containers.get(name)
            result.append(
                {
                    "name": name,
                    "status": c.status,
                    "restart_policy": c.attrs["HostConfig"]["RestartPolicy"]["Name"],
                    "managed": name in MANAGED_SERVICES,
                }
            )
        except NotFound:
            result.append(
                {
                    "name": name,
                    "status": "not_deployed",
                    "restart_policy": "",
                    "managed": False,
                }
            )
        except Exception as exc:
            result.append(
                {
                    "name": name,
                    "status": "error",
                    "restart_policy": "",
                    "managed": name in MANAGED_SERVICES,
                    "error": str(exc),
                }
            )
    client.close()
    return result


def _require_managed(name: str) -> None:
    if name not in MANAGED_SERVICES:
        raise ValueError(
            f"Service '{name}' is not manageable (allowed: {sorted(MANAGED_SERVICES)})"
        )


def disable_service(name: str) -> dict[str, Any]:
    """Stop a managed service and prevent auto-restart."""
    _require_managed(name)
    client = _client()
    try:
        c = client.containers.get(name)
        c.update(restart_policy={"Name": "no"})  # pyright: ignore[reportArgumentType]
        c.stop(timeout=10)
        logger.info("Disabled service: %s", name)
        return {"ok": True, "name": name, "action": "disable"}
    except NotFound:
        return {"ok": False, "error": f"Container '{name}' not found"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        client.close()


def enable_service(name: str) -> dict[str, Any]:
    """Re-enable a managed service with restart=always."""
    _require_managed(name)
    client = _client()
    try:
        c = client.containers.get(name)
        c.update(restart_policy={"Name": "always"})  # pyright: ignore[reportArgumentType]
        c.start()
        logger.info("Enabled service: %s", name)
        return {"ok": True, "name": name, "action": "enable"}
    except NotFound:
        return {"ok": False, "error": f"Container '{name}' not found"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        client.close()


def restart_service(name: str) -> dict[str, Any]:
    """Restart a managed service."""
    _require_managed(name)
    client = _client()
    try:
        c = client.containers.get(name)
        c.restart(timeout=10)
        logger.info("Restarted service: %s", name)
        return {"ok": True, "name": name, "action": "restart"}
    except NotFound:
        return {"ok": False, "error": f"Container '{name}' not found"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        client.close()
