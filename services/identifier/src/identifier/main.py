import asyncio
import logging
from typing import Any

from messaging.service import BaseService
from messaging.streams import SUBJECT_AUDIO_BACKFILL, SUBJECT_AUDIO_LIVE

logger = logging.getLogger("identifier")


class IdentifierService(BaseService):
    def __init__(self) -> None:
        super().__init__("identifier")

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        """
        Implementation of the Dual-Lane Pipeline for Identification.
        """
        self.logger.info("Identifier Service: Starting Dual Pipeline...")

        async with asyncio.TaskGroup() as tg:
            # Lane 1: Live Worker (High Priority)
            tg.create_task(self._live_worker(js, stop_event))

            # Lane 2: Backfill Worker (Background)
            tg.create_task(self._backfill_worker(js, stop_event))

            # Wait for shutdown signal
            await stop_event.wait()
            self.logger.info("Identifier Service: Shutdown signal received.")

    async def _live_worker(self, js: Any, stop_event: asyncio.Event) -> None:
        """
        Processes real-time audio for rapid identification.
        """
        try:
            # Subscribe to Live Audio
            # We use a pull subscription for reliability in v8.0
            sub = await js.subscribe(
                SUBJECT_AUDIO_LIVE,
                durable="identifier_live",
            )
            self.logger.info(f"Live Worker: Subscribed to {SUBJECT_AUDIO_LIVE}")

            while not stop_event.is_set():
                try:
                    msgs = await sub.fetch(1, timeout=1)
                    for msg in msgs:
                        # --- Identification Logic (OpenVINO Stub) ---
                        # Extract session_id from subject: audio.live.{session_id}
                        session_id = msg.subject.split(".")[-1]

                        # Stub: Emit identity event every few messages
                        # In reality, this would run vector lookup
                        # self.logger.debug(f"Live Worker: Identified segment for {session_id}")

                        await msg.ack()
                except TimeoutError:
                    continue
                except Exception as e:
                    self.logger.error(f"Live Worker Error: {e}")
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.critical(f"Live Worker Failed to initialize: {e}")

    async def _backfill_worker(self, js: Any, stop_event: asyncio.Event) -> None:
        """
        Processes historical audio from the pre-roll buffer.
        """
        try:
            # Subscribe to Backfill Audio
            sub = await js.subscribe(
                SUBJECT_AUDIO_BACKFILL,
                durable="identifier_backfill",
            )
            self.logger.info(f"Backfill Worker: Subscribed to {SUBJECT_AUDIO_BACKFILL}")

            while not stop_event.is_set():
                try:
                    msgs = await sub.fetch(1, timeout=1)
                    for msg in msgs:
                        # --- Identification Logic (OpenVINO Stub) ---
                        # session_id = msg.subject.split(".")[-1]
                        # self.logger.debug(f"Backfill Worker: Processing past audio for {session_id}")

                        await msg.ack()
                except TimeoutError:
                    continue
                except Exception as e:
                    self.logger.error(f"Backfill Worker Error: {e}")
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.critical(f"Backfill Worker Failed to initialize: {e}")


def main() -> None:
    service = IdentifierService()
    asyncio.run(service.start())


if __name__ == "__main__":
    main()
