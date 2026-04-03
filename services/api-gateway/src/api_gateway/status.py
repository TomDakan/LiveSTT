"""System status: service heartbeats, NATS stream stats, disk usage."""

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("api-gateway")

# Stream names to query (from messaging/streams.py)
_STREAM_NAMES = [
    "PRE_BUFFER",
    "AUDIO_STREAM",
    "TRANSCRIPTION_STREAM",
    "SESSION_STREAM",
    "CLASSIFICATION_STREAM",
]

_DB_PATH = Path(os.getenv("DB_PATH", "/data/db/livestt.db")).parent


async def get_system_status(js: Any) -> dict[str, Any]:
    """Gather system status from NATS KV, streams, and disk."""
    return {
        "services": await _get_service_heartbeats(js),
        "streams": await _get_stream_stats(js),
        "disk": _get_disk_usage(),
    }


_HEARTBEAT_STALE_S = 30.0  # mark service stale after 30s without heartbeat


async def _get_service_heartbeats(js: Any) -> list[dict[str, Any]]:
    """Read service_health KV bucket for live service status."""
    services: list[dict[str, Any]] = []
    now = time.time()
    try:
        kv = await js.key_value("service_health")
        keys = await kv.keys()
        for key in keys:
            try:
                entry = await kv.get(key)
                data = json.loads(entry.value.decode())
                ts = data.get("timestamp", 0)
                status = data.get("status", "unknown")
                if now - ts > _HEARTBEAT_STALE_S:
                    status = "stale"
                services.append(
                    {
                        "name": data.get("service", key),
                        "status": status,
                        "timestamp": ts,
                    }
                )
            except Exception:
                services.append({"name": key, "status": "error"})
    except Exception as exc:
        logger.debug(f"Could not read service_health KV: {exc}")
    return services


async def _get_stream_stats(js: Any) -> list[dict[str, Any]]:
    """Gather message count, bytes, and consumer count per stream."""
    stats: list[dict[str, Any]] = []
    for name in _STREAM_NAMES:
        try:
            info = await js.stream_info(name)
            stats.append(
                {
                    "name": name,
                    "messages": info.state.messages,
                    "bytes": info.state.bytes,
                    "consumers": info.state.consumer_count,
                }
            )
        except Exception:
            stats.append(
                {
                    "name": name,
                    "messages": 0,
                    "bytes": 0,
                    "consumers": 0,
                    "error": "unavailable",
                }
            )
    return stats


def _get_disk_usage() -> dict[str, Any]:
    """Return disk usage for the data directory."""
    db_path = _DB_PATH
    try:
        usage = shutil.disk_usage(db_path if db_path.exists() else ".")
        db_size = 0
        if db_path.exists():
            db_size = sum(f.stat().st_size for f in db_path.iterdir() if f.is_file())
        return {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "db_size_bytes": db_size,
        }
    except Exception:
        return {
            "total_bytes": 0,
            "used_bytes": 0,
            "free_bytes": 0,
            "db_size_bytes": 0,
        }
