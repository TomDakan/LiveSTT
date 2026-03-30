import asyncio
import contextlib
import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from messaging.streams import SESSION_KV_BUCKET
from nats.aio.client import Client as NATS
from nats.js.api import ConsumerConfig, DeliverPolicy
from pydantic import BaseModel

# --- Config ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-gateway")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
TRANSCRIPT_TOPIC = "transcript.final.>"
CONSUMER_DURABLE = "api_gateway"

# --- NATS Setup ---
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
        dead: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json({"type": "transcript", "payload": message})
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)

    async def broadcast_message(self, message: dict[str, Any]) -> None:
        """Broadcast a fully-formed typed message to all WebSocket clients."""
        dead: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)


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


async def _kv_watch_loop(session_kv: Any, config_kv: Any) -> None:
    """Watch session_state KV and broadcast status updates to WebSocket clients."""
    try:
        watcher = await session_kv.watch("current")
        async for entry in watcher:
            if entry is None:
                continue
            payload = await _build_status_payload(session_kv, config_kv, entry)
            await manager.broadcast_message(
                {"type": "session_status", "payload": payload}
            )
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning(f"KV watch loop error: {e}")


async def _build_status_payload(
    session_kv: Any,
    config_kv: Any,
    entry: Any | None = None,
) -> dict[str, Any]:
    """Build the session status payload (same shape as GET /session/status)."""
    state_data: dict[str, Any] = {"state": "idle"}

    if entry is not None:
        with contextlib.suppress(Exception):
            state_data = json.loads(entry.value.decode())
    else:
        try:
            e = await session_kv.get("current")
            state_data = json.loads(e.value.decode())
        except Exception:
            pass

    silence_timeout_s = 300
    try:
        cfg_entry = await config_kv.get("silence_timeout_s")
        silence_timeout_s = int(cfg_entry.value.decode())
    except Exception:
        pass

    result: dict[str, Any] = {
        "state": state_data.get("state", "idle"),
        "silence_timeout_s": silence_timeout_s,
    }
    if state_data.get("state") == "active":
        result["session_id"] = state_data.get("session_id")
        result["label"] = state_data.get("label", "")
        result["started_at"] = state_data.get("started_at")
    return result


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifecycle manager: connect NATS, start background tasks, clean up."""
    logger.info("API Gateway starting...")

    stop_event = asyncio.Event()
    pull_task: asyncio.Task[None] | None = None
    kv_watch_task: asyncio.Task[None] | None = None

    try:
        await nats_client.connect(NATS_URL, connect_timeout=5)
        logger.info(f"Connected to NATS at {NATS_URL}")

        js = nats_client.jetstream()

        # Transcript pull consumer
        sub = await js.pull_subscribe(
            TRANSCRIPT_TOPIC,
            durable=CONSUMER_DURABLE,
            config=ConsumerConfig(deliver_policy=DeliverPolicy.NEW),
        )
        logger.info(f"JetStream pull consumer '{CONSUMER_DURABLE}' on {TRANSCRIPT_TOPIC}")
        pull_task = asyncio.create_task(_pull_loop(sub, stop_event))

        # Session KV + config KV (read-only; audio-producer creates them)
        session_kv: Any | None = None
        config_kv: Any | None = None
        try:
            session_kv = await js.key_value(SESSION_KV_BUCKET)
            config_kv = await js.key_value("config")
            kv_watch_task = asyncio.create_task(_kv_watch_loop(session_kv, config_kv))
            logger.info("Session KV watch started")
        except Exception as e:
            logger.warning(f"Session KV unavailable at startup (non-fatal): {e}")

        # Subscribe to system.session events (core NATS push)
        async def _on_session_event(msg: Any) -> None:
            try:
                data = json.loads(msg.data.decode())
                await manager.broadcast_message(
                    {"type": "session_event", "payload": data}
                )
            except Exception as exc:
                logger.warning(f"session_event handler error: {exc}")

        async def _on_stt_status(msg: Any) -> None:
            try:
                data = json.loads(msg.data.decode())
                await manager.broadcast_message({"type": "stt_status", "payload": data})
            except Exception as exc:
                logger.warning(f"stt_status handler error: {exc}")

        await nats_client.subscribe("system.session", cb=_on_session_event)
        await nats_client.subscribe("system.stt_status", cb=_on_stt_status)

        # Store shared objects in app state for endpoint access
        app.state.nats = nats_client
        app.state.js = js
        app.state.session_kv = session_kv
        app.state.config_kv = config_kv

        yield

    finally:
        logger.info("Shutting down... closing NATS connection.")
        stop_event.set()
        for task in (pull_task, kv_watch_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        await nats_client.close()


_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

ALLOW_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Session models ---


class SessionStartBody(BaseModel):
    label: str = ""


# --- HTTP endpoints ---


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "api-gateway"}


@app.post("/session/start")
async def session_start(
    request: Request, body: SessionStartBody | None = None
) -> JSONResponse:
    """
    Start a new session. Unauthenticated — any audience member can start.
    Returns 409 if a session is already active.
    """
    session_kv = request.app.state.session_kv

    # Check for an already-active session
    if session_kv is not None:
        try:
            entry = await session_kv.get("current")
            data = json.loads(entry.value.decode())
            if data.get("state") == "active":
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": "session_already_active",
                        "session_id": data.get("session_id"),
                    },
                )
        except Exception:
            pass  # Key absent or unreadable → no active session

    label = body.label if body else ""
    command = json.dumps({"command": "start", "label": label}).encode()
    js = request.app.state.js
    await js.publish("session.control", command)
    return JSONResponse(content={"status": "ok"})


@app.post("/session/stop")
async def session_stop(request: Request) -> JSONResponse:
    """
    Stop the active session. Requires admin Bearer token.
    # TODO(M6.5): replace with JWT validation
    """
    admin_token = os.getenv("ADMIN_TOKEN", "")
    if admin_token:
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip()
        if token != admin_token:
            return JSONResponse(status_code=401, content={"error": "unauthorized"})
    else:
        logger.warning("ADMIN_TOKEN not set — accepting any token (dev mode)")

    js = request.app.state.js
    command = json.dumps({"command": "stop"}).encode()
    await js.publish("session.control", command)
    return JSONResponse(content={"status": "ok"})


@app.get("/session/status")
async def session_status(request: Request) -> dict[str, Any]:
    """Return the current session state and config."""
    session_kv = request.app.state.session_kv
    config_kv = request.app.state.config_kv

    if session_kv is None:
        return {"state": "idle"}

    return await _build_status_payload(session_kv, config_kv)


@app.websocket("/ws/transcripts")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    logger.info("Client connected to WebSocket.")

    try:
        while True:
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
