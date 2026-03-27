import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from messaging.service import BaseService
from messaging.streams import SUBJECT_AUDIO_BACKFILL, SUBJECT_AUDIO_LIVE

from .embedder import OpenVinoEmbedder
from .interfaces import Embedder, VoiceprintStore
from .store import LanceDBVoiceprintStore, StubVoiceprintStore

logger = logging.getLogger("identifier")

# 1.5 s window at 16 kHz (16 chunks × 1536 samples — see ADR-0012)
_WINDOW_SAMPLES: int = 24576
# Cosine distance threshold for accepting a speaker match
_MATCH_THRESHOLD: float = float(os.getenv("IDENTIFIER_THRESHOLD", "0.25"))


@dataclass
class _AudioBuffer:
    chunks: list[bytes] = field(default_factory=list)
    sample_count: int = 0

    def add(self, chunk: bytes) -> None:
        self.chunks.append(chunk)
        self.sample_count += len(chunk) // 2  # int16 = 2 bytes / sample

    def ready(self) -> bool:
        return self.sample_count >= _WINDOW_SAMPLES

    def consume(self) -> bytes:
        data = b"".join(self.chunks)
        self.chunks.clear()
        self.sample_count = 0
        return data


def _build_store() -> VoiceprintStore:
    try:
        return LanceDBVoiceprintStore()
    except Exception as e:
        logger.warning(f"LanceDB unavailable ({e}). Using StubVoiceprintStore.")
        return StubVoiceprintStore()


class IdentifierService(BaseService):
    def __init__(
        self,
        embedder: Embedder | None = None,
        store: VoiceprintStore | None = None,
    ) -> None:
        super().__init__("identifier")
        self._embedder: Embedder = embedder or OpenVinoEmbedder()
        self._store: VoiceprintStore = store or _build_store()

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        self.logger.info("Identifier starting dual-lane pipeline...")

        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._worker(js, stop_event, SUBJECT_AUDIO_LIVE, "live"))
            tg.create_task(
                self._worker(js, stop_event, SUBJECT_AUDIO_BACKFILL, "backfill")
            )

    async def _worker(
        self,
        js: Any,
        stop_event: asyncio.Event,
        subject: str,
        source: str,
    ) -> None:
        durable = f"identifier_{source}"
        try:
            sub = await js.pull_subscribe(subject, durable=durable)
            self.logger.info(f"{source} worker subscribed to {subject}")
        except Exception as e:
            self.logger.critical(f"{source} worker failed to subscribe: {e}")
            return

        buffers: dict[str, _AudioBuffer] = {}

        while not stop_event.is_set():
            try:
                msgs = await sub.fetch(1, timeout=1)
            except TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"{source} worker fetch error: {e}")
                await asyncio.sleep(1)
                continue

            for msg in msgs:
                session_id = msg.subject.split(".")[-1]
                buf = buffers.setdefault(session_id, _AudioBuffer())
                buf.add(msg.data)

                if buf.ready():
                    audio = buf.consume()
                    await self._identify_and_publish(js, audio, session_id, source)

                await msg.ack()

    async def _identify_and_publish(
        self,
        js: Any,
        audio_pcm: bytes,
        session_id: str,
        source: str,
    ) -> None:
        embedding = await asyncio.to_thread(self._embedder.embed, audio_pcm)
        if embedding is None:
            return  # No embedding — identity-manager will time out to Unknown

        result = await asyncio.to_thread(
            self._store.identify, embedding, _MATCH_THRESHOLD
        )
        if result is None:
            return  # No match — Unknown handled by identity-manager timeout

        speaker, confidence = result
        payload = {
            "speaker": speaker,
            "confidence": confidence,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        subject = f"transcript.identity.{source}"
        try:
            await js.publish(subject, json.dumps(payload).encode())
            self.logger.debug(f"Identified '{speaker}' ({confidence:.2f}) → {subject}")
        except Exception as e:
            self.logger.error(f"Failed to publish identity event: {e}")


def main() -> None:
    service = IdentifierService()
    asyncio.run(service.start())


if __name__ == "__main__":
    main()
