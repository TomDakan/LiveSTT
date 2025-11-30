import asyncio
import contextlib
import json
import logging
import os
from typing import Any

from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveOptions,
    LiveTranscriptionEvents,
)
from dotenv import load_dotenv
from nats.aio.client import Client as NATS

# --- Config ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stt-provider")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
TOPIC_INPUT = "audio.raw"
TOPIC_OUTPUT = "text.transcript"

# Audio Settings
ENCODING = "linear16"
CHANNELS = 1
SAMPLE_RATE = 16000


def get_api_key() -> str:
    key = os.getenv("DEEPGRAM_API_KEY")
    if not key:
        logger.error("DEEPGRAM_API_KEY not set.")
        raise ValueError("DEEPGRAM_API_KEY not set")
    return key


class STTService:
    def __init__(self) -> None:
        self.nc = NATS()
        self.audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.running = True
        self.api_key = get_api_key()

        # Initialize Deepgram Client (v3.x)
        config = DeepgramClientOptions(
            verbose=logging.WARNING,
        )
        self.dg_client = DeepgramClient(self.api_key, config)

    async def setup_nats(self) -> None:
        """Initialize NATS Connection."""
        try:
            await self.nc.connect(NATS_URL)
            logger.info(f"Connected to NATS at {NATS_URL}")

            # Subscribe to raw audio
            await self.nc.subscribe(TOPIC_INPUT, cb=self.on_audio_message)
            logger.info(f"Subscribed to {TOPIC_INPUT}")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def on_audio_message(self, msg: Any) -> None:
        """Callback for NATS audio messages."""
        try:
            # NATS message data is bytes
            await self.audio_queue.put(msg.data)
        except Exception as e:
            logger.error(f"Error queuing audio: {e}")

    async def deepgram_sender_loop(self) -> None:
        """
        Consumes the buffer and sends to Deepgram.
        Handles reconnection logic transparently.
        """
        logger.info("Starting Deepgram Sender Loop...")

        dg_options = LiveOptions(
            model="nova-2",
            language="en-US",
            smart_format=True,
            encoding=ENCODING,
            channels=CHANNELS,
            sample_rate=SAMPLE_RATE,
            interim_results=True,
        )

        while self.running:
            try:
                logger.info("Attempting connection to Deepgram...")

                # Create a new connection
                dg_connection = self.dg_client.listen.live.v("1")

                # Register Event Handlers
                dg_connection.on(LiveTranscriptionEvents.Transcript, self.on_transcript)
                dg_connection.on(LiveTranscriptionEvents.Error, self.on_error)

                # Start the socket
                if await dg_connection.start(dg_options) is False:
                    logger.error("Failed to start Deepgram connection. Retrying in 3s...")
                    await asyncio.sleep(3)
                    continue

                logger.info("Deepgram Connected. Streaming audio...")

                # Inner loop: Pump data from Queue -> Deepgram
                while self.running:
                    # Wait for audio data from the NATS callback
                    data = await self.audio_queue.get()

                    # Send to Deepgram
                    await dg_connection.send(data)

                    # Mark task as done for queue management
                    self.audio_queue.task_done()

            except Exception as e:
                logger.error(f"Deepgram connection lost: {e}. Reconnecting in 2s...")
                # We do NOT clear the self.audio_queue here.
                # This preserves audio data captured while we reconnect.
                await asyncio.sleep(2)
            finally:
                # Ensure we try to close the connection cleanly if possible
                with contextlib.suppress(Exception):
                    await dg_connection.finish()

    async def on_transcript(self, _: Any, result: Any, **kwargs: Any) -> None:
        """
        Callback when Deepgram returns a transcript.
        Publishes result back to NATS.
        """
        try:
            # Extract the transcript string
            sentence = result.channel.alternatives[0].transcript

            if len(sentence) == 0:
                return

            is_final = result.is_final

            # Payload structure
            payload = {
                "text": sentence,
                "is_final": is_final,
                "confidence": result.channel.alternatives[0].confidence,
            }

            # Publish to NATS
            await self.nc.publish(TOPIC_OUTPUT, json.dumps(payload).encode("utf-8"))

            if is_final:
                logger.debug(f"Published Final: {sentence}")

        except Exception as e:
            logger.error(f"Error processing transcript: {e}")

    def on_error(self, _: Any, error: Any, **kwargs: Any) -> None:
        logger.error(f"Deepgram Error Received: {error}")

    async def run(self) -> None:
        """Main entry point."""
        await self.setup_nats()

        # Run sender loop (ingestion is handled by NATS callback)
        sender_task = asyncio.create_task(self.deepgram_sender_loop())

        # Keep the main loop alive
        with contextlib.suppress(asyncio.CancelledError):
            # Wait for sender task or indefinitely
            await sender_task

    async def shutdown(self) -> None:
        self.running = False
        await self.nc.close()


if __name__ == "__main__":
    # Load .env if present (local dev)
    load_dotenv()

    service = STTService()
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("Stopping STT Provider...")
