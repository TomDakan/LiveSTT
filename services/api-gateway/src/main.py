import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import zmq
import zmq.asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- Config ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-gateway")

ZMQ_SUB_URL = os.getenv("ZMQ_SUB_URL", "tcp://broker:5556")
TRANSCRIPT_TOPIC = "text.transcript"

# --- ZMQ Setup ---
# Global context to be reused
zmq_ctx = zmq.asyncio.Context()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifecycle manager to handle ZMQ resource cleanup on shutdown.
    """
    logger.info("API Gateway starting...")
    yield
    logger.info("Shutting down... terminating ZMQ context.")
    zmq_ctx.term()


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
    Connects to ZMQ and streams transcripts to the browser.
    """
    await websocket.accept()
    logger.info("Client connected to WebSocket.")

    # Create a ZMQ Subscriber socket specifically for this connection
    # (Or use a shared queue pattern if you have many clients to reduce ZMQ overhead,
    # but one-socket-per-client is simplest for now)
    socket = zmq_ctx.socket(zmq.SUB)
    socket.connect(ZMQ_SUB_URL)
    socket.setsockopt_string(zmq.SUBSCRIBE, TRANSCRIPT_TOPIC)

    try:
        while True:
            # 1. Await ZMQ message
            msg = await socket.recv_multipart()
            # topic = msg[0].decode("utf-8")
            payload = msg[1].decode("utf-8")

            # 2. Parse JSON to ensure validity before forwarding
            data = json.loads(payload)

            # 3. Forward to WebSocket client
            # Structure: { "type": "transcript", "data": ... }
            await websocket.send_json({"type": "transcript", "payload": data})

    except WebSocketDisconnect:
        logger.info("Client disconnected.")
    except Exception as e:
        logger.error(f"Error in websocket loop: {e}")
    finally:
        # Clean up the ZMQ socket for this client
        socket.close()


if __name__ == "__main__":
    import uvicorn

    # Run on port 8000, bind to all interfaces for Docker
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)  # nosec B104
