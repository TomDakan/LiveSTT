import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from messaging.service import BaseService
from messaging.streams import TRANSCRIPTION_STREAM_CONFIG

logger = logging.getLogger("identity-manager")

# How long to wait for a matching identity before publishing with "Unknown"
PUBLISH_TIMEOUT_S: float = 3.0
# Max seconds between transcript and identity timestamps to consider a match
MATCH_WINDOW_S: float = 2.0
# Hard cap on in-memory buffers to prevent unbounded growth
MAX_BUFFER: int = 500


@dataclass
class _Pending:
    data: dict[str, Any]
    received_at: float  # monotonic loop time


def _parse_ts(iso_str: str | None) -> float | None:
    """Parse an ISO 8601 timestamp string to a POSIX float. Returns None on failure."""
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str).timestamp()
    except (ValueError, TypeError):
        return None


class IdentityManager(BaseService):
    """
    Time Zipper: fuses transcript.raw.* with transcript.identity.* and
    publishes to transcript.final.{source}.

    Interim transcripts are forwarded immediately (no identity wait needed).
    Final transcripts wait up to PUBLISH_TIMEOUT_S for a matching identity
    event, then publish with speaker="Unknown" if none arrives.

    When the identifier service is offline, all transcripts flow through
    with speaker="Unknown" so the rest of the pipeline continues to work.
    """

    def __init__(self) -> None:
        super().__init__("identity-manager")
        self._pending: list[_Pending] = []
        self._identities: list[dict[str, Any]] = []

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        try:
            await self.nats_manager.ensure_stream(**TRANSCRIPTION_STREAM_CONFIG)
            self.logger.info("Transcription stream verified")
        except Exception as e:
            self.logger.critical(f"Stream verification failed: {e}")
            return

        self.logger.info("Time Zipper starting...")
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._transcript_subscriber(js, stop_event))
            tg.create_task(self._identity_subscriber(js, stop_event))
            tg.create_task(self._fusion_loop(js, stop_event))

    # --- Subscribers ---

    async def _transcript_subscriber(self, js: Any, stop_event: asyncio.Event) -> None:
        try:
            sub = await js.subscribe("transcript.raw.>", durable="id_manager_raw")
            self.logger.info("Subscribed to transcript.raw.>")
        except Exception as e:
            self.logger.critical(f"Failed to subscribe to transcripts: {e}")
            return

        while not stop_event.is_set():
            try:
                msgs = await sub.fetch(1, timeout=1)
                for msg in msgs:
                    data = json.loads(msg.data.decode())
                    if data.get("is_final"):
                        self._pending.append(
                            _Pending(
                                data=data,
                                received_at=asyncio.get_running_loop().time(),
                            )
                        )
                        if len(self._pending) > MAX_BUFFER:
                            self._pending.pop(0)
                    else:
                        # Interim: forward immediately with no speaker tag
                        await self._publish(js, data, speaker=None)
                    await msg.ack()
            except TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Transcript subscriber error: {e}")

    async def _identity_subscriber(self, js: Any, stop_event: asyncio.Event) -> None:
        try:
            sub = await js.subscribe(
                "transcript.identity.>", durable="id_manager_identity"
            )
            self.logger.info("Subscribed to transcript.identity.>")
        except Exception as e:
            self.logger.critical(f"Failed to subscribe to identities: {e}")
            return

        while not stop_event.is_set():
            try:
                msgs = await sub.fetch(1, timeout=1)
                for msg in msgs:
                    data = json.loads(msg.data.decode())
                    self._identities.append(data)
                    if len(self._identities) > MAX_BUFFER:
                        self._identities.pop(0)
                    await msg.ack()
            except TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Identity subscriber error: {e}")

    # --- Fusion ---

    def _find_identity(self, transcript_ts: str | None) -> dict[str, Any] | None:
        """Return the closest identity event within MATCH_WINDOW_S, or None."""
        ts = _parse_ts(transcript_ts)
        if ts is None:
            return None

        best: dict[str, Any] | None = None
        best_diff = MATCH_WINDOW_S

        for identity in self._identities:
            id_ts = _parse_ts(identity.get("timestamp"))
            if id_ts is None:
                continue
            diff = abs(id_ts - ts)
            if diff < best_diff:
                best_diff = diff
                best = identity

        return best

    async def _fusion_loop(self, js: Any, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            now = asyncio.get_running_loop().time()
            still_pending: list[_Pending] = []

            for pending in self._pending:
                age = now - pending.received_at
                identity = self._find_identity(pending.data.get("timestamp"))

                if identity is not None or age >= PUBLISH_TIMEOUT_S:
                    speaker = (
                        identity.get("speaker", "Unknown") if identity else "Unknown"
                    )
                    await self._publish(js, pending.data, speaker=speaker)
                else:
                    still_pending.append(pending)

            self._pending = still_pending
            await asyncio.sleep(0.1)

    async def _publish(self, js: Any, data: dict[str, Any], speaker: str | None) -> None:
        source = data.get("source", "live")
        subject = f"transcript.final.{source}"
        payload = {**data, "speaker": speaker}
        try:
            await js.publish(subject, json.dumps(payload).encode())
        except Exception as e:
            self.logger.error(f"Failed to publish to {subject}: {e}")


def main() -> None:
    service = IdentityManager()
    asyncio.run(service.start())


if __name__ == "__main__":
    main()
