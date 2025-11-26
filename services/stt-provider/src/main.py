# ruff: noqa: PERF203
import asyncio
import contextlib
import json
import logging
import os

import zmq
import zmq.asyncio
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveOptions,
    LiveTranscriptionEvents,
)
from dotenv import load_dotenv

# --- Config ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stt-provider")

ZMQ_SUB_URL = os.getenv("ZMQ_SUB_URL", "tcp://broker:5555")
ZMQ_PUB_URL = os.getenv("ZMQ_PUB_URL", "tcp://broker:5556")
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
        self.ctx = zmq.asyncio.Context()
        self.audio_queue = asyncio.Queue()
        self.running = True
        self.api_key = get_api_key()

        # Initialize Deepgram Client (v3.x)
        # Note: DeepgramClientOptions is now passed as 'config'
        config = DeepgramClientOptions(
            verbose=logging.WARNING,
        )
        self.dg_client = DeepgramClient(self.api_key, config)

    async def setup_zmq(self):
        """Initialize ZMQ Sockets."""
        # Subscriber: Listens for Raw Audio
        self.sub_sock = self.ctx.socket(zmq.SUB)
        self.sub_sock.connect(ZMQ_SUB_URL)
        self.sub_sock.setsockopt(zmq.SUBSCRIBE, TOPIC_INPUT)
        logger.info(f"ZMQ Subscriber connected to {ZMQ_SUB_URL} (Topic: {TOPIC_INPUT})")

        # Publisher: Sends Transcripts
        self.pub_sock = self.ctx.socket(zmq.PUB)
        self.pub_sock.connect(ZMQ_PUB_URL)
        logger.info(f"ZMQ Publisher connected to {ZMQ_PUB_URL}")

    async def zmq_ingestion_loop(self):
        """
        High-reliability ingestion.
        Reads from ZMQ and buffers into RAM (asyncio.Queue).
        This continues running even if Deepgram is disconnected.
        """
        logger.info("Starting ZMQ Ingestion Loop...")
        while self.running:
            try:
                # Receive multipart: [topic, payload]
                # We assume payload is raw PCM bytes
                msg = await self.sub_sock.recv_multipart()
                # topic = msg[0]
                audio_data = msg[1]

                # Put into buffer. If queue is huge, we might need a drop strategy later.
                await self.audio_queue.put(audio_data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ZMQ Ingestion: {e}")
                await asyncio.sleep(0.1)

    async def deepgram_sender_loop(self):
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
                # If this loop breaks, we fall back to the outer loop (reconnect)
                while self.running:
                    # Wait for audio data from the ZMQ ingestion loop
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
                # Ensure we try to close the connection cleanly if possible
                with contextlib.suppress(Exception):
                    await dg_connection.finish()

    async def on_transcript(self, _, result, **kwargs):
        """
        Callback when Deepgram returns a transcript.
        Publishes result back to ZMQ.
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

            # Publish to ZMQ: [topic, json_string]
            # Note: zmq.asyncio sockets are thread-safe for async functions
            await self.pub_sock.send_multipart(
                [TOPIC_OUTPUT.encode("utf-8"), json.dumps(payload).encode("utf-8")]
            )

            if is_final:
                logger.debug(f"Published Final: {sentence}")

        except Exception as e:
            logger.error(f"Error processing transcript: {e}")

    def on_error(self, _, error, **kwargs):
        logger.error(f"Deepgram Error Received: {error}")

    async def run(self):
        """Main entry point."""
        await self.setup_zmq()

        # Run ingestion and sender concurrently
        ingestion_task = asyncio.create_task(self.zmq_ingestion_loop())
        sender_task = asyncio.create_task(self.deepgram_sender_loop())

        await asyncio.gather(ingestion_task, sender_task)

    async def shutdown(self):
        self.running = False
        self.ctx.term()


if __name__ == "__main__":
    # Load .env if present (local dev)
    load_dotenv()

    service = STTService()
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("Stopping STT Provider...")
