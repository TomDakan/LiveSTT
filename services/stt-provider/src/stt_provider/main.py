import asyncio
import contextlib
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

TranscriberFactory = type[Transcriber]

_RECONNECT_INITIAL_DELAY_S: float = 2.0
_RECONNECT_MAX_DELAY_S: float = 60.0
_DRAIN_TIMEOUT_S: float = 5.0
_DURABLE_LIVE = "stt_live"
_DURABLE_BACKFILL = "stt_backfill"

# --- Config ---
logging.basicConfig(level=logging.INFO)


@dataclass
class TranscriptPayload:
    text: str
    is_final: bool
    confidence: float
    timestamp: str  # ISO 8601
    source: str


class STTProviderService(BaseService):
    def __init__(self, transcriber_factory: TranscriberFactory | None = None) -> None:
        super().__init__("stt-provider")
        self._transcriber_factory: TranscriberFactory = (
            transcriber_factory or DeepgramTranscriber
        )

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        try:
            await self.nats_manager.ensure_stream(**TRANSCRIPTION_STREAM_CONFIG)
            self.logger.info("STT Streams Verified")
        except Exception as e:
            self.logger.critical(f"Stream verification failed: {e}")
            return

        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                self._run_lane(js, stop_event, SUBJECT_AUDIO_LIVE, _DURABLE_LIVE, "live")
            )
            tg.create_task(
                self._run_lane(
                    js, stop_event, SUBJECT_AUDIO_BACKFILL, _DURABLE_BACKFILL, "backfill"
                )
            )

    async def _connect_with_retry(
        self,
        source_tag: str,
        stop_event: asyncio.Event,
    ) -> Transcriber | None:
        """Connect to Deepgram with exponential backoff.

        Returns a connected Transcriber, or None if stop_event fires first.
        Audio is not fetched from NATS until this returns — providing natural
        offline buffering: messages accumulate in JetStream while Deepgram is
        unreachable and are replayed from the last ACKed position on reconnect.
        """
        dg_model = os.getenv("DEEPGRAM_MODEL", "nova-3")
        dg_encoding = os.getenv("DEEPGRAM_ENCODING", "linear16")
        delay = _RECONNECT_INITIAL_DELAY_S

        while not stop_event.is_set():
            try:
                transcriber = self._transcriber_factory()
                await transcriber.connect(model=dg_model, encoding=dg_encoding)
                self.logger.info(f"[{source_tag}] Connected to Deepgram")
                return transcriber
            except Exception as e:
                self.logger.warning(
                    f"[{source_tag}] Deepgram connect failed: {e}. "
                    f"Retrying in {delay:.0f}s"
                )
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=delay)
                    return None  # stop_event fired during backoff
                except TimeoutError:
                    pass
                delay = min(delay * 2, _RECONNECT_MAX_DELAY_S)

        return None

    async def _publish_stt_status(self, state: str, source_tag: str) -> None:
        """Publish Deepgram connection status on core NATS (non-JetStream)."""
        if self.nc is None:
            return
        try:
            payload = json.dumps({"state": state, "lane": source_tag}).encode()
            await self.nc.publish("system.stt_status", payload)
        except Exception as e:
            self.logger.warning(f"[{source_tag}] stt_status publish failed: {e}")

    async def _send_msgs(
        self,
        msgs: list[Any],
        transcriber: "Transcriber",
        source_tag: str,
        dg_closed: asyncio.Event,
    ) -> bool:
        """Send fetched messages to Deepgram; return True if EOS was received."""
        for msg in msgs:
            if msg.headers and msg.headers.get("LiveSTT-EOS") == "true":
                self.logger.info(
                    f"[{source_tag}] EOS received — closing Deepgram connection"
                )
                await msg.ack()
                dg_closed.set()
                return True
            try:
                await transcriber.send_audio(msg.data)
                await msg.ack()
            except Exception as e:
                self.logger.warning(f"[{source_tag}] send_audio failed: {e}")
                await self._publish_stt_status("reconnecting", source_tag)
                dg_closed.set()
                return False
        return False

    async def _run_lane(
        self,
        js: Any,
        stop_event: asyncio.Event,
        subject: str,
        durable: str,
        source_tag: str,
    ) -> None:
        """Pull-based lane: fetches audio only when Deepgram is connected.

        The durable consumer name ensures NATS tracks position across restarts,
        so audio buffered during an outage is automatically replayed.
        """
        try:
            sub = await js.pull_subscribe(subject, durable=durable)
            self.logger.info(f"[{source_tag}] Subscribed (durable={durable})")
        except Exception as e:
            self.logger.critical(f"[{source_tag}] subscribe failed: {e}")
            return

        while not stop_event.is_set():
            transcriber = await self._connect_with_retry(source_tag, stop_event)
            if transcriber is None:
                break

            await self._publish_stt_status("connected", source_tag)
            await self._check_consumer_lag(sub, js, source_tag)

            dg_closed = asyncio.Event()
            eos_received = False
            drain_task = asyncio.create_task(
                self._drain_events(transcriber, source_tag, js, stop_event, dg_closed)
            )

            try:
                while not stop_event.is_set() and not dg_closed.is_set():
                    try:
                        msgs = await sub.fetch(1, timeout=1)
                    except TimeoutError:
                        continue
                    except Exception as e:
                        self.logger.error(f"[{source_tag}] fetch error: {e}")
                        await asyncio.sleep(1)
                        continue

                    eos_received = await self._send_msgs(
                        msgs, transcriber, source_tag, dg_closed
                    )
            finally:
                await self._close_transcriber(transcriber, drain_task, source_tag)

            if not eos_received and not stop_event.is_set():
                await self._publish_stt_status("reconnecting", source_tag)

        self.logger.info(f"[{source_tag}] Lane stopped.")

    async def _close_transcriber(
        self,
        transcriber: Transcriber,
        drain_task: asyncio.Task[Any],
        source_tag: str,
    ) -> None:
        """Finish the Deepgram connection and drain any remaining events."""
        try:
            await transcriber.finish()
        except Exception as e:
            self.logger.warning(f"[{source_tag}] finish() failed: {e}")
        try:
            await asyncio.wait_for(drain_task, timeout=_DRAIN_TIMEOUT_S)
        except TimeoutError:
            self.logger.warning(f"[{source_tag}] drain_task timed out; cancelling")
            drain_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await drain_task

    async def _check_consumer_lag(self, sub: Any, js: Any, source_tag: str) -> None:
        """Log a warning if the consumer has fallen behind the stream head.

        Non-fatal: consumer info is advisory only (ADR-0011).
        """
        try:
            info = await sub.consumer_info()
            stream_info = await js.stream_info("AUDIO_STREAM")
            first_seq = stream_info.state.first_seq
            consumer_seq = info.delivered.stream_seq
            if consumer_seq < first_seq:
                gap_msgs = first_seq - consumer_seq
                lost_s = gap_msgs * 0.096
                self.logger.warning(
                    f"[{source_tag}] Audio gap detected: ~{lost_s:.0f}s of audio "
                    f"aged out during outage (consumer was at seq {consumer_seq}, "
                    f"stream now starts at {first_seq})"
                )
        except Exception as e:
            self.logger.debug(f"[{source_tag}] Could not check consumer lag: {e}")

    async def _drain_events(
        self,
        transcriber: Transcriber,
        source_tag: str,
        js: Any,
        stop_event: asyncio.Event,
        dg_closed: asyncio.Event,
    ) -> None:
        topic = f"{SUBJECT_PREFIX_TRANSCRIPT_RAW}.{source_tag}"
        async for event in transcriber.get_events():
            if stop_event.is_set():
                break
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
                self.logger.error(f"[{source_tag}] Failed to publish transcript: {e}")
        dg_closed.set()


if __name__ == "__main__":
    load_dotenv()
    service = STTProviderService()
    asyncio.run(service.start())
