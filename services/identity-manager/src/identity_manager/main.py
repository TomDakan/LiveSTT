import asyncio
import json
import logging
from typing import Any

from messaging.service import BaseService

logger = logging.getLogger("identity-manager")


class IdentityManager(BaseService):
    def __init__(self) -> None:
        super().__init__("identity-manager")
        # In-memory buffer for matching
        # Key: timestamp, Value: transcript object
        self.transcript_buffer: dict[float, dict[str, Any]] = {}
        # Key: timestamp, Value: identity object
        self.identity_buffer: dict[float, dict[str, Any]] = {}

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        """
        Subscribes to raw transcripts and identity events, fuses them, and publishes final results.
        """
        self.logger.info("Identity Manager: Starting Fusion Logic...")

        async with asyncio.TaskGroup() as tg:
            # Subscribe to Raw Transcripts
            tg.create_task(self._transcript_subscriber(js, stop_event))

            # Subscribe to Identity Events
            tg.create_task(self._identity_subscriber(js, stop_event))

            # Background Matcher Task
            tg.create_task(self._fusion_loop(stop_event))

            # Wait for shutdown signal
            await stop_event.wait()

    async def _transcript_subscriber(self, js: Any, stop_event: asyncio.Event) -> None:
        """
        Listens for transcript.raw.> events.
        """
        try:
            sub = await js.subscribe("transcript.raw.>", durable="id_manager_raw")
            self.logger.info("Subscribed to transcript.raw.>")

            while not stop_event.is_set():
                try:
                    msgs = await sub.fetch(1, timeout=1)
                    for msg in msgs:
                        data = json.loads(msg.data.decode())
                        # Standardize on a 'timestamp' field for matching
                        ts = data.get("timestamp", asyncio.get_running_loop().time())
                        self.transcript_buffer[ts] = data
                        await msg.ack()
                except TimeoutError:
                    continue
                except Exception as e:
                    self.logger.error(f"Transcript Sub Error: {e}")
        except Exception as e:
            self.logger.critical(f"Transcript Sub Failed: {e}")

    async def _identity_subscriber(self, js: Any, stop_event: asyncio.Event) -> None:
        """
        Listens for transcript.identity.> events.
        """
        try:
            sub = await js.subscribe(
                "transcript.identity.>", durable="id_manager_identity"
            )
            self.logger.info("Subscribed to transcript.identity.>")

            while not stop_event.is_set():
                try:
                    msgs = await sub.fetch(1, timeout=1)
                    for msg in msgs:
                        data = json.loads(msg.data.decode())
                        ts = data.get("timestamp", asyncio.get_running_loop().time())
                        self.identity_buffer[ts] = data
                        await msg.ack()
                except TimeoutError:
                    continue
                except Exception as e:
                    self.logger.error(f"Identity Sub Error: {e}")
        except Exception as e:
            self.logger.critical(f"Identity Sub Failed: {e}")

    async def _fusion_loop(self, stop_event: asyncio.Event) -> None:
        """
        Periodically attempts to match buffered transcripts with identities.
        """
        while not stop_event.is_set():
            try:
                # Matching logic:
                # For each transcript, find the closest identity within a time window.
                # If found, merge and publish. If not, maybe wait or publish with 'Unknown'.

                # Simple implementation:
                # Drain buffers and publish everything as 'final' for now
                # In a real system, we'd use fuzzy matching on timestamps.

                for ts in list(self.transcript_buffer.keys()):
                    transcript = self.transcript_buffer.pop(ts)
                    identity = self.identity_buffer.get(ts, {"speaker": "Unknown"})

                    # Fusion
                    final_result = {
                        **transcript,
                        "speaker": identity.get("speaker"),
                        "fused_at": asyncio.get_running_loop().time(),
                    }

                    # Publish to transcript.final.{session_id}
                    session_id = transcript.get("session_id", "default")
                    subject = f"transcript.final.{session_id}"

                    if self.js:
                        await self.js.publish(subject, json.dumps(final_result).encode())
                        # self.logger.debug(f"Published fused result: {subject}")

                await asyncio.sleep(0.5)
            except Exception as e:
                self.logger.error(f"Fusion Loop Error: {e}")
                await asyncio.sleep(1)


def main() -> None:
    service = IdentityManager()
    asyncio.run(service.start())


if __name__ == "__main__":
    main()
