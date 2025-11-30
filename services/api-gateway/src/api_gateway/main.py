import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from nats.aio.client import Client as NATS

# --- Config ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-gateway")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
TRANSCRIPT_TOPIC = "text.transcript"

# --- NATS Setup ---
# Global client to be reused
nc = NATS()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifecycle manager to handle NATS resource cleanup on shutdown.
    """
    logger.info("API Gateway starting...")
    try:
        await nc.connect(NATS_URL)
        logger.info(f"Connected to NATS at {NATS_URL}")
        yield
    finally:
        logger.info("Shutting down... closing NATS connection.")
        await nc.close()


app = FastAPI(lifespan=lifespan)

# Enable CORS (adjust origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "api-gateway"}


@app.websocket("/ws/transcripts")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for UI clients.
    Connects to NATS and streams transcripts to the browser.
    """
    await websocket.accept()
    logger.info("Client connected to WebSocket.")

    async def message_handler(msg):
        try:
            payload = msg.data.decode("utf-8")
            data = json.loads(payload)
            await websocket.send_json({"type": "transcript", "payload": data})
        except Exception as e:
            logger.error(f"Error forwarding message: {e}")

    try:
        # Subscribe to the topic
        # We use a unique subscription for each client to keep it simple,
        # but for high scale we might want a shared subscription broadcasting to all
        # websockets.
        sub = await nc.subscribe(TRANSCRIPT_TOPIC, cb=message_handler)

        # Keep the connection open until client disconnects
        while True:
            # We just wait here; the callback handles the sending.
            # Receiving a message from the client (e.g. ping) keeps it alive.
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("Client disconnected.")
    except Exception as e:
        logger.error(f"Error in websocket loop: {e}")
    finally:
        # NATS subscription is automatically cleaned up if we unsubscribe or if connection
        # closes, but explicit unsubscribe is good practice if we reused the connection.
        # Since 'sub' is local scope, we can't easily unsubscribe here without tracking
        # it, but the 'lifespan' manages the main connection.
        # For per-request subscriptions, we should ideally unsubscribe.
        with suppress(Exception):
            if "sub" in locals():
                await sub.unsubscribe()
