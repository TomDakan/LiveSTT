import asyncio
import logging
import os
from typing import Any

from messaging.service import BaseService

_DEFAULT_MONITORED = (
    "audio-producer,stt-provider,identity-manager,audio-classifier,api-gateway"
)
MONITORED_SERVICES: list[str] = [
    s.strip()
    for s in os.getenv("MONITORED_SERVICES", _DEFAULT_MONITORED).split(",")
    if s.strip()
]
HEALTH_BUCKET = "service_health"
CHECK_INTERVAL_S: float = 10.0


class HealthWatchdog(BaseService):
    def __init__(self) -> None:
        super().__init__("health-watchdog")

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        self.logger.info("Health Watchdog starting...")

        while not stop_event.is_set():
            await self._check_services(js)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=CHECK_INTERVAL_S)
            except TimeoutError:
                continue

    async def _check_services(self, js: Any) -> None:
        try:
            kv = await js.key_value(HEALTH_BUCKET)
        except Exception:
            self.logger.warning(
                f"KV bucket '{HEALTH_BUCKET}' not yet available — "
                "waiting for services to start"
            )
            return

        try:
            alive: set[str] = set(await kv.keys())
        except Exception as e:
            self.logger.error(f"Failed to list service health keys: {e}")
            return

        for service in MONITORED_SERVICES:
            if service not in alive:
                self.logger.warning(f"Health Alert: {service} is DOWN (no heartbeat)")

        unexpected = alive - set(MONITORED_SERVICES) - {"health-watchdog"}
        for service in sorted(unexpected):
            self.logger.info(f"{service}: running (not in monitored list)")


def main() -> None:
    service = HealthWatchdog()
    asyncio.run(service.start())


if __name__ == "__main__":
    main()
