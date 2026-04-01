import array
import asyncio
import contextlib
import json
import math
import os
from datetime import UTC, datetime
from typing import Any

from messaging.service import BaseService
from messaging.streams import (
    AUDIO_STREAM_CONFIG,
    PREROLL_STREAM_CONFIG,
    SESSION_KV_BUCKET,
    SESSION_STREAM_CONFIG,
    SUBJECT_PREFIX_AUDIO_BACKFILL,
    SUBJECT_PREFIX_AUDIO_LIVE,
    SUBJECT_PREFIX_PREROLL,
)
from nats.js.api import ConsumerConfig, DeliverPolicy, KeyValueConfig

# Import the module itself so we can safely check for platform-specific classes
from . import audiosource
from .interfaces import AudioSource

SILENCE_THRESHOLD_DBFS: float = -50.0
_DEFAULT_SILENCE_TIMEOUT_S: int = 300


def _compute_rms(data: bytes) -> float:
    """Compute RMS level of int16 PCM data in dBFS. Returns -inf for silence."""
    n = len(data) // 2
    if n == 0:
        return -math.inf
    samples = array.array("h", data)
    sum_sq = sum(s * s for s in samples)
    rms = math.sqrt(sum_sq / n)
    if rms == 0.0:
        return -math.inf
    return 20.0 * math.log10(rms / 32768.0)


class AudioProducerService(BaseService):
    def __init__(self) -> None:
        super().__init__("audio-producer")
        self.session_id: str | None = None
        self.is_active = False
        self.silence_samples: int = 0
        self.silence_timeout_s: int = _DEFAULT_SILENCE_TIMEOUT_S
        self._label: str = ""
        self._session_kv: Any | None = None
        self._config_kv: Any | None = None
        self._background_tasks: set[asyncio.Task[None]] = set()

    def _get_audio_source(self) -> AudioSource:
        """
        Factory method to select the correct Audio Source based on
        Env Vars and Platform availability.
        """
        # 1. High Priority: File Override (for Testing/Simulation)
        audio_file = os.getenv("AUDIO_FILE")
        if audio_file:
            self.logger.info(f"Source: File ({audio_file})")
            return audiosource.FileSource(audio_file, chunk_size=1536, loop=True)

        # 2. Windows Microphone
        if hasattr(audiosource, "WindowsSource"):
            self.logger.info("Source: Windows Microphone (PyAudio)")
            return audiosource.WindowsSource()

        # 3. Linux Microphone
        if hasattr(audiosource, "LinuxSource"):
            self.logger.info("Source: Linux Microphone (ALSA)")
            return audiosource.LinuxSource(sample_rate=16000, chunk_size=1536)

        # 4. Fallback / Error
        raise RuntimeError(
            "No valid Audio Source found! "
            "Set AUDIO_FILE env var or ensure PyAudio/ALSA is installed."
        )

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        # 1. Ensure Streams Exist
        try:
            await self.nats_manager.ensure_stream(**PREROLL_STREAM_CONFIG)
            await self.nats_manager.ensure_stream(**AUDIO_STREAM_CONFIG)
            await self.nats_manager.ensure_stream(**SESSION_STREAM_CONFIG)
            self.logger.info("Audio Streams Verified")
        except Exception as e:
            self.logger.critical(f"Failed to verify streams: {e}")
            return

        # 2. Setup KV buckets (non-fatal if unavailable)
        try:
            self._session_kv = await js.create_key_value(
                config=KeyValueConfig(bucket=SESSION_KV_BUCKET, history=1)
            )
            self._config_kv = await js.create_key_value(
                config=KeyValueConfig(bucket="config", history=1)
            )
            self.logger.info("Session KV buckets ready")
        except Exception as e:
            self.logger.warning(f"KV setup failed (non-fatal): {e}")

        # 2b. Recover session state from KV on restart
        await self._recover_session()

        # 3. Initialize the appropriate audio source
        try:
            source = self._get_audio_source()
        except Exception as e:
            self.logger.critical(f"Failed to initialize audio source: {e}")
            return

        self.logger.info("Audio Stream Started")

        # 4. Run session control listener as a background task
        ctrl_task: asyncio.Task[None] | None = None
        ctrl_task = asyncio.create_task(self._session_control_loop(js, stop_event))

        try:
            await self._audio_loop(js, stop_event, source)
        finally:
            if ctrl_task is not None and not ctrl_task.done():
                ctrl_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await ctrl_task

    async def _recover_session(self) -> None:
        """On restart, check KV for an active session and resume if found."""
        if self._session_kv is None:
            return
        try:
            entry = await self._session_kv.get("current")
            data = json.loads(entry.value.decode())
            if data.get("state") == "active":
                self.session_id = data["session_id"]
                self.is_active = True
                self._label = data.get("label", "")
                self.logger.info(f"Resuming session {self.session_id}")
        except Exception:  # nosec B110
            pass  # Key absent or parse error → remain IDLE

    async def _handle_control_message(self, js: Any, msg: Any) -> None:
        """Process a single session control message and ack it."""
        try:
            data = json.loads(msg.data.decode())
        except Exception:
            await msg.ack()
            return

        command = data.get("command")
        if command == "start":
            if self.is_active:
                self.logger.warning("Received start command but session already active")
            else:
                await self._start_session(js, data.get("label", ""))
        elif command == "stop" and self.is_active:
            await self._stop_session(js)
        await msg.ack()

    async def _session_control_loop(self, js: Any, stop_event: asyncio.Event) -> None:
        """Durable pull consumer for session.control commands."""
        try:
            sub = await js.pull_subscribe(
                "session.control",
                durable="audio_producer_ctrl",
            )
            self.logger.info("Session control subscriber ready")
        except Exception as e:
            self.logger.critical(f"Session control subscribe failed: {e}")
            return

        while not stop_event.is_set():
            try:
                msgs = await sub.fetch(1, timeout=1)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error(f"Session control fetch error: {e}")
                await asyncio.sleep(0)
                continue

            for msg in msgs:
                await self._handle_control_message(js, msg)

    async def _start_session(self, js: Any, label: str = "") -> None:
        session_id = datetime.now(UTC).strftime("%Y%m%d-%H%M")
        started_at = datetime.now(UTC).isoformat()

        if self._session_kv is not None:
            try:
                kv_data = json.dumps(
                    {
                        "session_id": session_id,
                        "started_at": started_at,
                        "state": "active",
                        "label": label,
                    }
                ).encode()
                await self._session_kv.put("current", kv_data)
            except Exception as e:
                self.logger.warning(f"KV write failed: {e}")

        self.session_id = session_id
        self.is_active = True
        self._label = label

        # Read silence timeout from config KV (default if absent)
        self.silence_timeout_s = _DEFAULT_SILENCE_TIMEOUT_S
        if self._config_kv is not None:
            try:
                entry = await self._config_kv.get("silence_timeout_s")
                self.silence_timeout_s = int(entry.value.decode())
            except Exception:  # nosec B110
                pass

        self.silence_samples = 0

        # Spawn pre-roll flush as concurrent background task
        task = asyncio.create_task(self._flush_preroll(js, session_id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Publish session lifecycle event on core NATS
        if self.nc is not None:
            event = json.dumps(
                {
                    "event": "started",
                    "session_id": session_id,
                    "started_at": started_at,
                    "label": label,
                }
            ).encode()
            try:
                await self.nc.publish("system.session", event)
            except Exception as e:
                self.logger.warning(f"Failed to publish session started event: {e}")

        self.logger.info(f"Session started: {session_id}")

    async def _stop_session(self, js: Any) -> None:
        session_id = self.session_id
        stopped_at = datetime.now(UTC).isoformat()

        # 1. Publish EOS marker to live audio stream
        if session_id:
            try:
                await js.publish(
                    f"{SUBJECT_PREFIX_AUDIO_LIVE}.{session_id}",
                    b"",
                    headers={"LiveSTT-EOS": "true"},
                )
            except Exception as e:
                self.logger.warning(f"Failed to publish EOS marker: {e}")

        # 2. Transition to IDLE
        self.is_active = False
        self.session_id = None
        self._label = ""

        # 3. Clear session KV
        if self._session_kv is not None:
            try:
                await self._session_kv.delete("current")
            except Exception as e:
                self.logger.warning(f"KV delete failed: {e}")

        # 4. Publish session lifecycle event
        if self.nc is not None:
            event = json.dumps(
                {
                    "event": "stopped",
                    "session_id": session_id,
                    "stopped_at": stopped_at,
                }
            ).encode()
            try:
                await self.nc.publish("system.session", event)
            except Exception as e:
                self.logger.warning(f"Failed to publish session stopped event: {e}")

        self.logger.info(f"Session stopped: {session_id}")

    async def _flush_preroll(self, js: Any, session_id: str) -> None:
        """Backfill pre-roll ring buffer into audio.backfill.<session_id>."""
        try:
            sub = await js.pull_subscribe(
                SUBJECT_PREFIX_PREROLL,
                config=ConsumerConfig(
                    deliver_policy=DeliverPolicy.ALL,
                    filter_subject=SUBJECT_PREFIX_PREROLL,
                ),
            )
        except Exception as e:
            self.logger.warning(f"Pre-roll flush subscribe failed: {e}")
            return

        count = 0
        while True:
            try:
                msgs = await sub.fetch(50, timeout=1)
                if not msgs:
                    break
                for msg in msgs:
                    await js.publish(
                        f"{SUBJECT_PREFIX_AUDIO_BACKFILL}.{session_id}",
                        msg.data,
                    )
                    await msg.ack()
                    count += 1
            except TimeoutError:
                break
            except Exception as e:
                self.logger.error(f"Pre-roll flush error: {e}")
                break

        # Signal end of backfill stream
        try:
            await js.publish(
                f"{SUBJECT_PREFIX_AUDIO_BACKFILL}.{session_id}",
                b"",
                headers={"LiveSTT-EOS": "true"},
            )
        except Exception as e:
            self.logger.warning(f"Failed to publish backfill EOS: {e}")

        self.logger.info(
            f"Pre-roll flush complete: {count} chunks → audio.backfill.{session_id}"
        )

    async def _audio_loop(
        self, js: Any, stop_event: asyncio.Event, source: AudioSource
    ) -> None:
        async with source as stream:
            async for chunk in stream.stream():
                if stop_event.is_set():
                    break

                if self.is_active and self.session_id:
                    try:
                        await js.publish(
                            f"{SUBJECT_PREFIX_AUDIO_LIVE}.{self.session_id}",
                            chunk,
                        )
                        await self._check_silence(js, chunk)
                    except Exception as e:
                        self.logger.error(f"Publish failed (chunk dropped): {e}")
                        continue
                else:
                    try:
                        await js.publish(SUBJECT_PREFIX_PREROLL, chunk)
                    except Exception as e:
                        self.logger.error(f"Publish failed (chunk dropped): {e}")
                        continue

        # Audio source exhausted — signal stop so control loop exits too
        if not stop_event.is_set():
            stop_event.set()

    async def _check_silence(self, js: Any, chunk: bytes) -> None:
        """Track cumulative silence; auto-stop session when threshold is reached."""
        rms = _compute_rms(chunk)
        if rms < SILENCE_THRESHOLD_DBFS:
            self.silence_samples += len(chunk) // 2
        else:
            self.silence_samples = 0

        silence_s = self.silence_samples / 16000
        if silence_s >= self.silence_timeout_s:
            self.logger.info(f"Auto-stop: {silence_s:.0f}s of silence detected")
            await self._stop_session(js)


def main() -> None:
    service = AudioProducerService()
    asyncio.run(service.start())


if __name__ == "__main__":
    main()
