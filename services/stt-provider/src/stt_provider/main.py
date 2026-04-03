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
    SUBJECT_PREFIX_TRANSCRIPT_INTERIM,
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

        await self._run_session_loop(js, stop_event)

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

    @staticmethod
    def _session_id_from_subject(subject: str) -> str | None:
        """Extract session ID from 'audio.{backfill|live}.<sid>'."""
        parts = subject.rsplit(".", 1)
        return parts[-1] if len(parts) >= 2 else None

    async def _send_msgs(
        self,
        msgs: list[Any],
        transcriber: "Transcriber",
        source_tag: str,
        dg_closed: asyncio.Event,
        close_on_eos: bool = True,
        session_id: str | None = None,
    ) -> bool:
        """Send fetched messages to Deepgram; return True if EOS was received.

        When close_on_eos is False the Deepgram connection is kept open after
        the EOS marker — the caller switches the audio phase instead.
        Messages from a different session are ACKed and skipped.
        """
        for msg in msgs:
            # Skip stale messages from a previous session
            if session_id and hasattr(msg, "subject"):
                msg_sid = self._session_id_from_subject(msg.subject)
                if msg_sid and msg_sid != session_id:
                    await msg.ack()
                    continue

            if msg.headers and msg.headers.get("LiveSTT-EOS") == "true":
                self.logger.info(f"[{source_tag}] EOS received")
                await msg.ack()
                if close_on_eos:
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

    async def _wait_for_audio(
        self,
        sub: Any,
        stop_event: asyncio.Event,
        source_tag: str,
    ) -> list[Any]:
        """Block until audio arrives on the NATS subject.

        Prevents Deepgram connections while idle (no session active),
        avoiding the idle-timeout / reconnect loop.
        """
        while not stop_event.is_set():
            try:
                return list(await sub.fetch(1, timeout=2))
            except TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"[{source_tag}] fetch error: {e}")
                await asyncio.sleep(1)
        return []

    async def _fetch_phase(
        self,
        sub: Any,
        transcriber: Transcriber,
        source_tag: str,
        dg_closed: asyncio.Event,
        stop_event: asyncio.Event,
        first_msgs: list[Any],
        close_on_eos: bool,
        session_id: str | None = None,
    ) -> bool:
        """Drain one NATS subject into the open Deepgram connection.

        Returns True when EOS is received, False when the connection drops or
        stop_event fires.
        """
        eos = await self._send_msgs(
            first_msgs,
            transcriber,
            source_tag,
            dg_closed,
            close_on_eos,
            session_id,
        )
        if eos or dg_closed.is_set():
            return eos

        while not stop_event.is_set() and not dg_closed.is_set():
            try:
                msgs = list(await sub.fetch(1, timeout=1))
            except TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"[{source_tag}] fetch error: {e}")
                await asyncio.sleep(1)
                continue

            eos = await self._send_msgs(
                msgs,
                transcriber,
                source_tag,
                dg_closed,
                close_on_eos,
                session_id,
            )
            if eos or dg_closed.is_set():
                return eos

        return False

    async def _run_session_loop(
        self,
        js: Any,
        stop_event: asyncio.Event,
    ) -> None:
        """Subscribe once to both subjects and loop over sessions.

        Each session: drain backfill → switch to live on the same Deepgram
        connection → close when live EOS or disconnect.
        """
        try:
            backfill_sub = await js.pull_subscribe(
                SUBJECT_AUDIO_BACKFILL, durable=_DURABLE_BACKFILL
            )
            self.logger.info(f"Subscribed to backfill (durable={_DURABLE_BACKFILL})")
            live_sub = await js.pull_subscribe(SUBJECT_AUDIO_LIVE, durable=_DURABLE_LIVE)
            self.logger.info(f"Subscribed to live (durable={_DURABLE_LIVE})")
        except Exception as e:
            self.logger.critical(f"Subscribe failed: {e}")
            return

        while not stop_event.is_set():
            # Phase 1: wait for the first backfill message (signals a new session)
            first_bf_msgs = await self._wait_for_audio(
                backfill_sub, stop_event, "backfill"
            )
            if stop_event.is_set():
                break

            # Extract session ID from the first message's subject
            session_id: str | None = None
            if first_bf_msgs and hasattr(first_bf_msgs[0], "subject"):
                session_id = self._session_id_from_subject(first_bf_msgs[0].subject)
            self.logger.info(f"New session detected: {session_id}")

            transcriber = await self._connect_with_retry("live", stop_event)
            if transcriber is None:
                break

            await self._publish_stt_status("connected", "live")
            await self._check_consumer_lag(backfill_sub, js, "backfill")

            dg_closed = asyncio.Event()
            # tag_holder[0] is read dynamically by _drain_events so that
            # transcript subjects switch from "backfill" to "live" mid-stream.
            tag_holder: list[str] = ["backfill"]
            drain_task = asyncio.create_task(
                self._drain_events(transcriber, tag_holder, js, stop_event, dg_closed)
            )

            try:
                # Phase 2: send backfill audio; keep DG connection open on EOS
                bf_eos = await self._fetch_phase(
                    backfill_sub,
                    transcriber,
                    "backfill",
                    dg_closed,
                    stop_event,
                    first_bf_msgs,
                    close_on_eos=False,
                    session_id=session_id,
                )

                # Phase 3: live audio on the same DG connection
                if not dg_closed.is_set() and not stop_event.is_set():
                    if bf_eos:
                        # Normal path: backfill finished, move to live
                        tag_holder[0] = "live"
                        first_live_msgs = await self._wait_for_audio(
                            live_sub, stop_event, "live"
                        )
                        if not stop_event.is_set():
                            await self._fetch_phase(
                                live_sub,
                                transcriber,
                                "live",
                                dg_closed,
                                stop_event,
                                first_live_msgs,
                                close_on_eos=True,
                                session_id=session_id,
                            )
                    else:
                        # DG dropped during backfill — no live phase this cycle
                        pass
            finally:
                await self._close_transcriber(transcriber, drain_task, "live")

            if not stop_event.is_set() and dg_closed.is_set():
                # Only publish reconnecting if DG closed unexpectedly (not on EOS)
                pass

        self.logger.info("Session loop stopped.")

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
        tag_holder: list[str],
        js: Any,
        stop_event: asyncio.Event,
        dg_closed: asyncio.Event,
    ) -> None:
        assert self.nc is not None  # guaranteed after BaseService.start()
        async for event in transcriber.get_events():
            if stop_event.is_set():
                break
            source_tag = tag_holder[0]
            topic = f"{SUBJECT_PREFIX_TRANSCRIPT_RAW}.{source_tag}"
            interim_topic = f"{SUBJECT_PREFIX_TRANSCRIPT_INTERIM}.{source_tag}"
            payload_obj = TranscriptPayload(
                text=event.text,
                is_final=event.is_final,
                confidence=event.confidence,
                timestamp=datetime.now(UTC).isoformat(),
                source=source_tag,
            )
            encoded = json.dumps(dataclasses.asdict(payload_obj)).encode("utf-8")
            try:
                if event.is_final:
                    await js.publish(topic, encoded)
                else:
                    await self.nc.publish(interim_topic, encoded)
            except Exception as e:
                self.logger.error(f"[{source_tag}] Failed to publish transcript: {e}")
        dg_closed.set()


if __name__ == "__main__":
    load_dotenv()
    service = STTProviderService()
    asyncio.run(service.start())
