import asyncio
import json
import logging
import signal
from abc import ABC, abstractmethod
from typing import Any

from messaging.nats import NatsJSManager
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from nats.js.api import KeyValueConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)


class BaseService(ABC):
    def __init__(self, service_name: str, nats_url: str = "nats://nats:4222") -> None:
        self.service_name = service_name
        self.nats_url = nats_url
        self.stop_event = asyncio.Event()
        self.logger = logging.getLogger(service_name)

        # Use your library class here
        self.nats_manager = NatsJSManager()

        # These will be populated after start()
        self.nc: NATS | None = None
        self.js: JetStreamContext | None = None
        self.kv: Any | None = None

    @abstractmethod
    async def run_business_logic(
        self, js: JetStreamContext | Any, stop_event: asyncio.Event
    ) -> None:
        """
        Child classes MUST implement this.
        Args:
            js: The Raw NATS JetStream context
            stop_event: Signal to stop loops
        """
        pass

    async def _heartbeat_task(self) -> None:
        """Standard Heartbeat Loop"""
        if not self.js:
            self.logger.warning("Heartbeat skipped: JS not connected")
            return

        try:
            # Create KV bucket if missing — run once at startup.
            self.kv = await self.js.create_key_value(
                config=KeyValueConfig(
                    bucket="service_health",
                    ttl=5 * 1000000000,  # 5s TTL
                )
            )
        except Exception as e:
            self.logger.warning(f"Heartbeat KV init failed (non-fatal): {e}")
            return

        self.logger.info("Heartbeat initialized")

        while not self.stop_event.is_set():
            try:
                payload = json.dumps(
                    {
                        "status": "running",
                        "service": self.service_name,
                        "timestamp": asyncio.get_running_loop().time(),
                    }
                ).encode()
                await self.kv.put(self.service_name, payload)
                await asyncio.sleep(2)
            except Exception as e:
                self.logger.warning(f"Heartbeat tick failed (will retry): {e}")
                await asyncio.sleep(2)

    async def start(self) -> None:
        """Lifecycle Manager"""
        # 1. Handle OS Signals
        loop = asyncio.get_running_loop()
        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: self.stop_event.set())
        except NotImplementedError:
            # Windows ProactorEventLoop does not support add_signal_handler
            self.logger.info(
                "Windows detected: Signal handlers skipped. Relying on KeyboardInterrupt."
            )

        # 2. Connect using your shared logic
        try:
            # Expose raw NC and JS to the service
            self.nc, self.js = await self.nats_manager.connect(self.nats_url)
        except Exception as e:
            self.logger.critical(f"NATS Connection failed: {e}")
            return

        # 3. Run TaskGroup
        try:
            self.logger.info("Starting Service Tasks...")
            async with asyncio.TaskGroup() as tg:
                # Task A: The Heartbeat (Background)
                tg.create_task(self._heartbeat_task())

                # Task B: The Actual Service Logic (Your Code)
                tg.create_task(self.run_business_logic(self.js, self.stop_event))

                # Block here until signal received
                await self.stop_event.wait()
                self.logger.info("Shutdown signal received. Stopping tasks...")
        except (KeyboardInterrupt, asyncio.CancelledError):
            self.logger.info("Service cancelled/interrupted. Shutting down...")
            self.stop_event.set()
            # TaskGroup will now exit and cancel remaining tasks
        except Exception as e:
            self.logger.critical(f"Service Crashed: {e}")
            raise
        finally:
            # 4. Cleanup using your shared logic
            await self.nats_manager.close()
