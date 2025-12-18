import asyncio
import json
from dataclasses import asdict
from typing import Any

from dotenv import load_dotenv
from messaging.service import BaseService
from messaging.streams import (
    CLASSIFICATION_STREAM_CONFIG,
    SUBJECT_AUDIO_LIVE,
    SUBJECT_PREFIX_CLASSIFICATION,
)

from .classifiers import OpenVinoClassifier


class AudioClassifierService(BaseService):
    def __init__(self) -> None:
        super().__init__("audio-classifier")
        self.classifier = OpenVinoClassifier()  # Will fallback if needed

    async def run_business_logic(self, js: Any, stop_event: asyncio.Event) -> None:
        # 1. Ensure Output Stream
        try:
            await self.nats_manager.ensure_stream(**CLASSIFICATION_STREAM_CONFIG)
            self.logger.info("Classification Stream Verified")
        except Exception as e:
            self.logger.critical(f"Stream verification failed: {e}")
            return

        # 2. Subscribe to Audio
        await js.subscribe(
            subject=SUBJECT_AUDIO_LIVE,
            queue="audio-classifier-group",
            cb=self._handle_audio,
        )
        self.logger.info(f"Subscribed to {SUBJECT_AUDIO_LIVE}")

        # 3. Keep alive until stopped
        await stop_event.wait()

    async def _handle_audio(self, msg: Any) -> None:
        if not self.js:
            return

        try:
            audio_data = msg.data
            # Classify
            result = self.classifier.classify(audio_data)

            # Publish result
            payload = asdict(result)
            topic = f"{SUBJECT_PREFIX_CLASSIFICATION}.live"

            await self.js.publish(topic, json.dumps(payload).encode("utf-8"))

        except Exception as e:
            self.logger.error(f"Error processing audio chunk: {e}")


def main() -> None:
    load_dotenv()
    service = AudioClassifierService()
    asyncio.run(service.start())


if __name__ == "__main__":
    main()
