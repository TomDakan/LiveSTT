import asyncio
import logging
import os

from dotenv import load_dotenv
from messaging.nats import JetStreamClient

from .deepgram_adapter import DeepgramTranscriber
from .service import STTService

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


class Main:
    async def run(self) -> None:
        # 1. Setup Dependencies
        nats_client = JetStreamClient()
        # Ensure we connect first
        await nats_client.connect(NATS_URL)

        # Configurable retention for text stream (Default 7 days)
        text_retention = float(os.getenv("NATS_TEXT_RETENTION", "604800"))

        # Ensure text stream exists
        await nats_client.ensure_stream(
            "text", ["text.transcript", "identity.event", "events.merged"], text_retention
        )

        transcriber = DeepgramTranscriber()

        # 2. Create Service
        service = STTService(nats=nats_client, transcriber=transcriber)

        # 3. Run Service
        await service.start()


if __name__ == "__main__":
    # Load .env if present (local dev)
    load_dotenv()

    main = Main()
    try:
        asyncio.run(main.run())
    except KeyboardInterrupt:
        logger.info("Stopping STT Provider...")
        pass
