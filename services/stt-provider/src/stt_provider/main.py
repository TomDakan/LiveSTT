import asyncio
import contextlib
import json
import logging
import os
from typing import Any

from deepgram import AsyncDeepgramClient
from dotenv import load_dotenv
from nats.aio.client import Client as NATS

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
        nats_client = NATS()
        # We need to adapt the NATS client to our protocol if needed,
        # but our protocol matches the nats-py client mostly.
        # However, our Service expects an object that has .connect(), .subscribe(), .publish(), .close()
        # The nats-py client has these.

        transcriber = DeepgramTranscriber() # Assuming DeepgramTranscriber can be instantiated without API key, or gets it internally

        # 2. Create Service
        service = STTService(nats=nats_client, transcriber=transcriber)

        # 3. Run Service
        # Note: service.start() is an infinite loop in our current implementation (due to _event_loop awaiting)
        # We should probably run it.
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
