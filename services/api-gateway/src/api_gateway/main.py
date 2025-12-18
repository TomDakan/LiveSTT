import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from nats.aio.client import Client as NATS

# --- Config ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-gateway")

from messaging.streams import SUBJECT_TRANSCRIPT_RAW

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
TRANSCRIPT_TOPIC = SUBJECT_TRANSCRIPT_RAW

# --- NATS Setup ---
# We will inject this into the app state
nats_client = NATS()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        # Broadcast to all connected clients
        # Iterate over a copy to avoid modification issues if disconnects happen during send (though unlikely in this sync loop)
        for connection in list(self.active_connections):
            try:
                await connection.send_json({"type": "transcript", "payload": message})
            except Exception:
                # If send fails, assume disconnected or error; cleanup might be handled by endpoint,
                # but let's be safe. Real cleanup happens in disconnect() called by endpoint.
                pass


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifecycle manager to handle NATS resource cleanup on shutdown.
    """
    logger.info("API Gateway starting...")

    async def nats_callback(msg: Any) -> None:
        try:
            payload = msg.data.decode("utf-8")
            data = json.loads(payload)
            await manager.broadcast(data)
        except Exception as e:
            logger.error(f"Error broadcasting NATS message: {e}")

    try:
        await nats_client.connect(NATS_URL, connect_timeout=5)
        logger.info(f"Connected to NATS at {NATS_URL}")

        # Global Subscription
        await nats_client.subscribe(TRANSCRIPT_TOPIC, cb=nats_callback)
        logger.info(f"Subscribed to {TRANSCRIPT_TOPIC} (Broadcast Mode)")

        # Store in app state for access in endpoints
        app.state.nats = nats_client
        yield
    finally:
        logger.info("Shutting down... closing NATS connection.")
        await nats_client.close()


app = FastAPI(lifespan=lifespan)

# Enable CORS (adjust origins for production)
# Enable CORS (adjust origins for production)
ALLOW_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
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
    await manager.connect(websocket)
    logger.info("Client connected to WebSocket.")

    try:
        while True:
            # We just wait here to keep connection open
            # Receiving a message from the client (e.g. ping) keeps it alive.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected.")
    except Exception as e:
        manager.disconnect(websocket)
        logger.error(f"Error in websocket loop: {e}")


def main() -> None:
    """Entry point for the application script."""
    import uvicorn

    reload = os.getenv("DEV_MODE", "false").lower() == "true"
    uvicorn.run("api_gateway.main:app", host="0.0.0.0", port=8000, reload=reload)  # nosec B104


if __name__ == "__main__":
    main()
