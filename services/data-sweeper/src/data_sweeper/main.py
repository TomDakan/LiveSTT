import asyncio
import logging
from typing import Any

from messaging.service import BaseService

logger = logging.getLogger("data-sweeper")


class DataSweeper(BaseService):
    def __init__(self) -> None:
        super().__init__("data-sweeper")
        # How often to run cleanup (e.g., every 30 mins)
        self.cleanup_interval = 1800  # 30 minutes

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        """
        Periodically cleans up old JetStream data.
        """
        self.logger.info("Data Sweeper: Starting Cleanup Loop...")

        while not stop_event.is_set():
            try:
                # Logic: Atomic Clean-up (Stub for now)
                # In v8.0, JetStream handles most retention (LIMITS),
                # but we might want to manually purge orphaned streams/consumers.
                self.logger.info("Data Sweeper: Running periodic cleanup...")

                # Simulate cleanup work
                await asyncio.sleep(2)

                self.logger.info("Data Sweeper: Cleanup complete.")

                # Wait for the next interval or stop signal
                try:
                    await asyncio.wait_for(
                        stop_event.wait(), timeout=self.cleanup_interval
                    )
                except TimeoutError:
                    continue  # Interval passed, run again
            except Exception as e:
                self.logger.error(f"Cleanup Error: {e}")
                await asyncio.sleep(60)


def main() -> None:
    service = DataSweeper()
    asyncio.run(service.start())


if __name__ == "__main__":
    main()
