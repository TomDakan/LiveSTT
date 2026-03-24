import asyncio
import json
import logging
import time
from typing import Any

from messaging.service import BaseService

logger = logging.getLogger("health-watchdog")


class HealthWatchdog(BaseService):
    def __init__(self) -> None:
        super().__init__("health-watchdog")
        # Registry of heartbeats: {service_name: last_seen_timestamp}
        self.registry: dict[str, float] = {}
        # Threshold for status: "Stale" if no heartbeat for 15s
        self.stale_threshold = 15.0

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        """
        Monitors heartbeats from all services and logs health status.
        """
        self.logger.info("Health Watchdog: Starting Monitor...")

        async with asyncio.TaskGroup() as tg:
            # Task 1: Listen for all heartbeats
            tg.create_task(self._heartbeat_listener(stop_event))

            # Task 2: Periodic Health Check
            tg.create_task(self._health_check_loop(stop_event))

            # Wait for shutdown signal
            await stop_event.wait()
            self.logger.info("Health Watchdog: Shutdown signal received.")

    async def _heartbeat_listener(self, stop_event: asyncio.Event) -> None:
        """
        Subscribes to all heartbeat topics.
        """
        if not self.nc:
            return

        # Simple NATS subscription (not JetStream) for real-time heartbeats
        sub = await self.nc.subscribe("service.heartbeat.>", cb=self._handle_heartbeat)
        self.logger.info("Heartbeat Listener: Subscribed to service.heartbeat.>")

        await stop_event.wait()
        await sub.unsubscribe()

    async def _handle_heartbeat(self, msg: Any) -> None:
        """
        Processes an individual heartbeat message.
        """
        try:
            data = json.loads(msg.data.decode())
            service_name = data.get("service", "unknown")
            self.registry[service_name] = time.time()
            # self.logger.debug(f"Received heartbeat from {service_name}")
        except Exception as e:
            self.logger.error(f"Error handling heartbeat: {e}")

    async def _health_check_loop(self, stop_event: asyncio.Event) -> None:
        """
        Periodically reviews the registry for stale services.
        """
        while not stop_event.is_set():
            try:
                now = time.time()
                stale_services = []

                for name, last_seen in self.registry.items():
                    if now - last_seen > self.stale_threshold:
                        stale_services.append(name)

                if stale_services:
                    self.logger.warning(
                        f"Health Alert: Stale services detected: {stale_services}"
                    )
                else:
                    # self.logger.info("Health Check: All services OK")
                    pass

                await asyncio.sleep(10)  # Check every 10 seconds
            except Exception as e:
                self.logger.error(f"Health Check Loop Error: {e}")
                await asyncio.sleep(5)


def main() -> None:
    service = HealthWatchdog()
    asyncio.run(service.start())


if __name__ == "__main__":
    main()
