import asyncio
import json
import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from messaging.service import BaseService
from messaging.streams import (
    AUDIO_STREAM_CONFIG,
    CLASSIFICATION_STREAM_CONFIG,
    PREROLL_STREAM_CONFIG,
    TRANSCRIPTION_STREAM_CONFIG,
)

REPORT_INTERVAL_S: float = 1800.0  # 30 minutes
SCHEDULE_CHECK_INTERVAL_S: float = 30.0
MONITORED_STREAMS: list[str] = [
    str(PREROLL_STREAM_CONFIG["name"]),
    str(AUDIO_STREAM_CONFIG["name"]),
    str(TRANSCRIPTION_STREAM_CONFIG["name"]),
    str(CLASSIFICATION_STREAM_CONFIG["name"]),
]

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api-gateway:8000")
SITE_TIMEZONE = os.getenv("SITE_TIMEZONE", "UTC")


class SystemManager(BaseService):
    def __init__(self) -> None:
        super().__init__("system-manager")
        self._last_fired: dict[str, str] = {}
        self._last_report: float = 0.0

    async def _handle_service_control(self, msg: Any) -> None:
        """Handle NATS request/reply for service management."""
        try:
            data = json.loads(msg.data.decode())
        except Exception:
            await msg.respond(json.dumps({"ok": False, "error": "invalid JSON"}).encode())
            return

        from system_manager.containers import (
            disable_service,
            enable_service,
            list_services,
            restart_service,
        )

        action = data.get("action", "")
        service = data.get("service", "")

        if action == "list":
            result = {"ok": True, "services": list_services()}
        elif action == "enable":
            result = enable_service(service)
        elif action == "disable":
            result = disable_service(service)
        elif action == "restart":
            result = restart_service(service)
        else:
            result = {"ok": False, "error": f"Unknown action: {action}"}

        await msg.respond(json.dumps(result).encode())

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        self.logger.info("System Manager starting...")

        # Subscribe to service control requests (core NATS request/reply)
        if self.nc is not None:
            await self.nc.subscribe(
                "system.service_control",
                cb=self._handle_service_control,
            )
            self.logger.info("Service control handler registered")

        while not stop_event.is_set():
            # Stream stats (every 30 minutes)
            now_mono = asyncio.get_event_loop().time()
            if now_mono - self._last_report >= REPORT_INTERVAL_S:
                await self._report_stream_stats(js)
                self._last_report = now_mono

            # Schedule checks (every 30 seconds)
            await self._check_schedules(js)

            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=SCHEDULE_CHECK_INTERVAL_S,
                )
            except TimeoutError:
                continue

    async def _check_schedules(self, js: Any) -> None:
        """Fetch schedules from api-gateway and fire if due."""
        try:
            tz = ZoneInfo(SITE_TIMEZONE)
        except Exception:
            self.logger.warning(f"Invalid SITE_TIMEZONE: {SITE_TIMEZONE}")
            return

        now = datetime.now(tz)
        current_dow = (now.weekday() + 1) % 7  # 0=Sun
        current_hhmm = now.strftime("%H:%M")

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{API_GATEWAY_URL}/admin/schedules")
                if resp.status_code != 200:
                    return
                schedules = resp.json()
        except Exception as e:
            self.logger.debug(f"Could not fetch schedules: {e}")
            return

        for sched in schedules:
            await self._eval_schedule(js, sched, now, current_dow, current_hhmm)

        # Prune old fire keys (keep only today's)
        today = now.strftime("%Y%m%d")
        self._last_fired = {k: v for k, v in self._last_fired.items() if today in k}

    async def _eval_schedule(
        self,
        js: Any,
        sched: dict[str, Any],
        now: datetime,
        current_dow: int,
        current_hhmm: str,
    ) -> None:
        """Evaluate a single schedule and fire if due."""
        if not sched.get("enabled", True):
            return
        sched_id = sched["id"]
        days = sched.get("day_of_week", [])
        if current_dow not in days:
            return

        fire_key = f"{sched_id}:{now.strftime('%Y%m%d')}"

        if current_hhmm == sched["start_time"]:
            start_key = f"start:{fire_key}"
            if start_key not in self._last_fired:
                await self._fire_start(js, sched, now)
                self._last_fired[start_key] = current_hhmm

        if current_hhmm == sched["stop_time"]:
            stop_key = f"stop:{fire_key}"
            if stop_key not in self._last_fired:
                await self._fire_stop(js, sched)
                self._last_fired[stop_key] = current_hhmm

    async def _fire_start(self, js: Any, sched: dict[str, Any], now: datetime) -> None:
        """Publish a scheduled session start command."""
        template = sched.get("label_template", "")
        label = template.replace("{date}", now.strftime("%B %d"))
        command = json.dumps(
            {
                "command": "start",
                "label": label,
                "scheduled": True,
            }
        ).encode()
        try:
            await js.publish("session.control", command)
            self.logger.info(f"Scheduled start fired: {sched['id']} — {label!r}")
        except Exception as e:
            self.logger.error(f"Failed to fire scheduled start: {e}")

    async def _fire_stop(self, js: Any, sched: dict[str, Any]) -> None:
        """Publish a scheduled session stop command."""
        policy = sched.get("stop_policy", "soft")
        if policy == "soft":
            self.logger.info(f"Scheduled stop skipped (soft policy): {sched['id']}")
            return

        command = json.dumps({"command": "stop"}).encode()
        try:
            await js.publish("session.control", command)
            self.logger.info(f"Scheduled stop fired: {sched['id']}")
        except Exception as e:
            self.logger.error(f"Failed to fire scheduled stop: {e}")

    async def _report_stream_stats(self, js: Any) -> None:
        for stream_name in MONITORED_STREAMS:
            try:
                info = await js.stream_info(stream_name)
                state = info.state
                self.logger.info(
                    f"{stream_name}: {state.messages} msgs, "
                    f"{state.bytes / 1024:.1f} KB, "
                    f"{state.consumer_count} consumers"
                )
            except Exception as e:
                self.logger.warning(f"{stream_name}: unavailable ({e})")


def main() -> None:
    service = SystemManager()
    asyncio.run(service.start())


if __name__ == "__main__":
    main()
