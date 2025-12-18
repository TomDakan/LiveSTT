import asyncio
import dataclasses
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv
from messaging.service import BaseService
from messaging.streams import (
    SUBJECT_AUDIO_BACKFILL,
    SUBJECT_AUDIO_LIVE,
    SUBJECT_PREFIX_TRANSCRIPT_RAW,
    TRANSCRIPTION_STREAM_CONFIG,
)

from .deepgram_adapter import DeepgramTranscriber
from .interfaces import Transcriber


@dataclass
class TranscriptPayload:
    text: str
    is_final: bool
    confidence: float
    timestamp: str  # ISO 8601
    source: str


# --- Config ---
logging.basicConfig(level=logging.INFO)


class STTProviderService(BaseService):
    def __init__(self) -> None:
        super().__init__("stt-provider")
        self.live_transcriber: Transcriber | None = None
        self.backfill_transcriber: Transcriber | None = None

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        # 1. Ensure Output Streams
        try:
            await self.nats_manager.ensure_stream(**TRANSCRIPTION_STREAM_CONFIG)
            self.logger.info("STT Streams Verified")
        except Exception as e:
            self.logger.critical(f"Stream verification failed: {e}")
            return

        # 2. Setup Transcribers (Dual Pipeline)
        self.live_transcriber = DeepgramTranscriber()
        self.backfill_transcriber = DeepgramTranscriber()

        try:
            # Connect both
            # Load config (basic env var support for now, can be expanded to typed-settings later)
            dg_model = os.getenv("DEEPGRAM_MODEL", "nova-3")
            dg_encoding = os.getenv("DEEPGRAM_ENCODING", "linear16")

            await self.live_transcriber.connect(model=dg_model, encoding=dg_encoding)
            await self.backfill_transcriber.connect(model=dg_model, encoding=dg_encoding)
            self.logger.info("Connected to Deepgram (Dual Pipeline)")
        except Exception as e:
            self.logger.critical(f"Deepgram connection failed: {e}")
            return

        # 3. Setup Consumers
        # A. Live Consumer
        await js.subscribe(
            subject=SUBJECT_AUDIO_LIVE,
            queue="stt-live-group",
            cb=self._handle_live_audio,
        )
        self.logger.info("Subscribed to audio.live.>")

        # B. Backfill Consumer
        await js.subscribe(
            subject=SUBJECT_AUDIO_BACKFILL,
            queue="stt-backfill-group",
            cb=self._handle_backfill_audio,
        )
        self.logger.info("Subscribed to audio.backfill.>")

        # 4. Process Transcripts (Merged Loop)
        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                self._process_events(self.live_transcriber, "live", stop_event, js)
            )
            tg.create_task(
                self._process_events(
                    self.backfill_transcriber, "backfill", stop_event, js
                )
            )

    async def _handle_live_audio(self, msg: Any) -> None:
        if self.live_transcriber:
            await self.live_transcriber.send_audio(msg.data)

    async def _handle_backfill_audio(self, msg: Any) -> None:
        if self.backfill_transcriber:
            await self.backfill_transcriber.send_audio(msg.data)

    async def _process_events(
        self,
        transcriber: Transcriber | None,
        source_tag: str,
        stop_event: asyncio.Event,
        js: Any,
    ) -> None:
        """Generic event processor for a transcriber."""
        if not transcriber:
            return

        async for event in transcriber.get_events():
            if stop_event.is_set():
                break

            # Enrich
            topic = f"{SUBJECT_PREFIX_TRANSCRIPT_RAW}.{source_tag}"
            payload_obj = TranscriptPayload(
                text=event.text,
                is_final=event.is_final,
                confidence=event.confidence,
                timestamp=datetime.now(UTC).isoformat(),
                source=source_tag,
            )
            payload = dataclasses.asdict(payload_obj)
            try:
                await js.publish(topic, json.dumps(payload).encode("utf-8"))
            except Exception as e:
                self.logger.error(f"Failed to publish {source_tag} transcript: {e}")

        # Cleanup when done
        await transcriber.finish()


if __name__ == "__main__":
    load_dotenv()
    service = STTProviderService()
    asyncio.run(service.start())  # type: ignore
