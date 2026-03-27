import asyncio
import contextlib
import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from nats.aio.client import Client as NATS
from nats.js.api import ConsumerConfig, DeliverPolicy

# --- Config ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-gateway")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
TRANSCRIPT_TOPIC = "transcript.final.>"
CONSUMER_DURABLE = "api_gateway"

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
        # Iterate over copy to avoid modification issues
        for connection in list(self.active_connections):
            with contextlib.suppress(Exception):
                await connection.send_json({"type": "transcript", "payload": message})


manager = ConnectionManager()


async def _pull_loop(sub: Any, stop_event: asyncio.Event) -> None:
    """Pull transcript messages from JetStream and broadcast to WebSocket clients."""
    while not stop_event.is_set():
        try:
            msgs = await sub.fetch(10, timeout=1)
            for msg in msgs:
                try:
                    data = json.loads(msg.data.decode("utf-8"))
                    await manager.broadcast(data)
                except Exception as e:
                    logger.error(f"Error broadcasting NATS message: {e}")
                await msg.ack()
        except TimeoutError:
            continue
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Pull consumer error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifecycle manager to handle NATS resource cleanup on shutdown.
    """
    logger.info("API Gateway starting...")

    stop_event = asyncio.Event()
    pull_task: asyncio.Task[None] | None = None

    try:
        await nats_client.connect(NATS_URL, connect_timeout=5)
        logger.info(f"Connected to NATS at {NATS_URL}")

        js = nats_client.jetstream()
        sub = await js.pull_subscribe(
            TRANSCRIPT_TOPIC,
            durable=CONSUMER_DURABLE,
            config=ConsumerConfig(deliver_policy=DeliverPolicy.NEW),
        )
        logger.info(f"JetStream pull consumer '{CONSUMER_DURABLE}' on {TRANSCRIPT_TOPIC}")

        pull_task = asyncio.create_task(_pull_loop(sub, stop_event))

        # Store in app state for access in endpoints
        app.state.nats = nats_client
        yield
    finally:
        logger.info("Shutting down... closing NATS connection.")
        stop_event.set()
        if pull_task is not None:
            pull_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pull_task
        await nats_client.close()


_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

# Enable CORS (adjust origins for production)
ALLOW_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


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
