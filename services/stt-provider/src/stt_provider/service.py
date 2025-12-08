import json
import logging
import os
from typing import Any

from messaging.nats import NatsClient

from .interfaces import Transcriber

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

logger = logging.getLogger(__name__)


class STTService:
    """
    Core service logic.
    Bridges NATS audio stream -> Transcriber -> NATS transcript stream.
    """

    def __init__(
        self,
        nats: NatsClient,
        transcriber: Transcriber,
        input_subject: str = "audio.raw",
        output_subject: str = "text.transcript",
    ) -> None:
        self.nats = nats
        self.transcriber = transcriber
        self.input_subject = input_subject
        self.output_subject = output_subject
        self.running = False

    async def start(self) -> None:
        """
        Starts the service.
        1. Connects to NATS.
        2. Connects to Transcriber.
        3. Subscribes to audio.
        4. Starts the event loop to publish transcripts.
        """
        # Connect to NATS if not already connected
        if not getattr(self.nats, "js", None):
            await self.nats.connect(NATS_URL)

        await self.transcriber.connect()
        # Durable consumer ensures we pick up where we left off
        await self.nats.subscribe(
            self.input_subject, cb=self._on_audio_message, durable="stt-provider-consumer"
        )
        self.running = True
        await self._event_loop()

    async def stop(self) -> None:
        """Stops the service and cleans up resources."""
        self.running = False
        # Only close if we manage it? It's DI, so maybe not.
        # But legacy behavior was closing.
        # Ideally, we verify if we should close.
        # For now, let's close it to match previous behavior, assuming we own it.
        await self.nats.close()
        await self.transcriber.finish()

    async def _on_audio_message(self, msg: Any) -> None:
        """Callback for incoming NATS audio messages."""
        await self.transcriber.send_audio(msg.data)
        if not self.running:
            await self.stop()

    async def _event_loop(self) -> None:
        """
        Consumes events from the transcriber and publishes them to NATS.
        Should run concurrently.
        """
        async for event in self.transcriber.get_events():
            payload = {
                "text": event.text,
                "is_final": event.is_final,
                "confidence": event.confidence,
            }
            try:
                await self.nats.publish(
                    self.output_subject, json.dumps(payload).encode("utf-8")
                )
            except Exception as e:
                logger.error(f"Failed to publish transcript: {e}")
            if not self.running:
                await self.stop()
