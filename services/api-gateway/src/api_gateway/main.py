import asyncio
import collections
import contextlib
import json
import logging
import os
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from messaging.streams import SESSION_KV_BUCKET
from nats.aio.client import Client as NATS
from nats.js.api import ConsumerConfig, DeliverPolicy
from pydantic import BaseModel
from sqlalchemy import select, update

from api_gateway.auth import create_token, require_admin, verify_password
from api_gateway.db import (
    LogEntry,
    Schedule,
    SessionModel,
    TranscriptSegment,
    create_engine_and_tables,
)

# --- Log ring buffer & persistence config ---
_LOG_RING_SIZE = 500  # In-memory ring buffer replayed on WebSocket connect
_LOG_PERSIST_LEVELS = set(
    os.getenv("LOG_PERSIST_LEVELS", "ERROR,CRITICAL").upper().split(",")
)
_LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))
_log_ring: collections.deque[dict[str, Any]] = collections.deque(maxlen=_LOG_RING_SIZE)
_log_subscribers: list[asyncio.Queue[dict[str, Any]]] = []

# Maximum number of log messages buffered per /admin/logs WebSocket client.
# When the buffer is full, the oldest message is dropped.
_LOG_WS_QUEUE_SIZE = 200

# --- Config ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-gateway")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
MAX_WS_CONNECTIONS = int(os.getenv("MAX_WS_CONNECTIONS", "50"))
SITE_URL = os.getenv("SITE_URL", "")
TRANSCRIPT_TOPIC = "transcript.final.>"
CONSUMER_DURABLE = "api_gateway"

# --- NATS Setup ---
nats_client = NATS()

# Tracks the active session ID for transcript persistence.
# Updated by the KV watcher and session event handler.
_active_session_id: str | None = None


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


async def _pull_loop(sub: Any, stop_event: asyncio.Event, db_factory: Any) -> None:
    """Pull transcript messages from JetStream and broadcast to WebSocket clients."""
    while not stop_event.is_set():
        try:
            msgs = await sub.fetch(10, timeout=1)
            for msg in msgs:
                try:
                    data = json.loads(msg.data.decode("utf-8"))
                    await manager.broadcast(data)
                    if data.get("is_final") and _active_session_id:
                        await _persist_segment(db_factory, _active_session_id, data)
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
        except Exception:  # nosec B110
            pass

    silence_timeout_s = 300
    try:
        cfg_entry = await config_kv.get("silence_timeout_s")
        silence_timeout_s = int(cfg_entry.value.decode())
    except Exception:  # nosec B110
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


async def _on_interim_transcript(msg: Any) -> None:
    """Forward interim transcripts from core NATS to WebSocket clients."""
    try:
        data = json.loads(msg.data.decode())
        if not data.get("is_final", True):
            await manager.broadcast(data)
    except Exception as exc:
        logger.warning(f"interim transcript handler error: {exc}")


async def _persist_segment(
    db_factory: Any, session_id: str, data: dict[str, Any]
) -> None:
    """Write a final transcript segment to the database."""
    try:
        async with db_factory() as db:
            segment = TranscriptSegment(
                session_id=session_id,
                timestamp=data.get("timestamp", ""),
                speaker=data.get("speaker", "Unknown"),
                text=data.get("text", ""),
                confidence=data.get("confidence", 0.0),
                source=data.get("source", "live"),
            )
            db.add(segment)
            await db.commit()
    except Exception as exc:
        logger.warning(f"Failed to persist segment: {exc}")


async def _handle_session_db(db_factory: Any, data: dict[str, Any]) -> None:
    """Create or update a session row based on lifecycle events."""
    global _active_session_id
    event = data.get("event")
    session_id = data.get("session_id")
    if not session_id:
        return

    try:
        async with db_factory() as db:
            if event == "started":
                # Check if session already exists (e.g. from recovery)
                existing = await db.execute(
                    select(SessionModel).where(SessionModel.id == session_id)
                )
                if existing.scalar_one_or_none() is None:
                    row = SessionModel(
                        id=session_id,
                        label=data.get("label", ""),
                        started_at=data.get("started_at", ""),
                        scheduled=(1 if data.get("scheduled") else 0),
                    )
                    db.add(row)
                    await db.commit()
                _active_session_id = session_id
            elif event == "stopped":
                await db.execute(
                    update(SessionModel)
                    .where(SessionModel.id == session_id)
                    .values(stopped_at=data.get("stopped_at", ""))
                )
                await db.commit()
                _active_session_id = None
    except Exception as exc:
        logger.warning(f"Failed to persist session event: {exc}")


async def _kv_connect_and_watch(
    app: FastAPI,
    js: Any,
    stop_event: asyncio.Event,
) -> None:
    """Retry KV bucket connection, recover session, then watch."""
    global _active_session_id
    while not stop_event.is_set():
        try:
            session_kv = await js.key_value(SESSION_KV_BUCKET)
            config_kv = await js.key_value("config")
            app.state.session_kv = session_kv
            app.state.config_kv = config_kv
            # Recover active session ID from KV
            try:
                entry = await session_kv.get("current")
                kv_data = json.loads(entry.value.decode())
                if kv_data.get("state") == "active":
                    _active_session_id = kv_data.get("session_id")
                    logger.info(f"Recovered active session: {_active_session_id}")
            except Exception:  # nosec B110
                pass
            logger.info("Session KV watch started")
            await _kv_watch_loop(session_kv, config_kv)
            return
        except Exception as e:
            logger.debug(f"Session KV not ready: {e}")
            await asyncio.sleep(2)


async def _on_session_event(msg: Any) -> None:
    """Handle session lifecycle events from audio-producer.

    Persists session start/stop to the database. The KV watcher
    (_kv_watch_loop) is the authoritative path for WebSocket status
    broadcasts — the session_event broadcast was removed as it was
    unused by all UI clients.
    """
    try:
        data = json.loads(msg.data.decode())
        db_factory = _lifespan_db_factory
        if db_factory is not None:
            await _handle_session_db(db_factory, data)
    except Exception as exc:
        logger.warning(f"session_event handler error: {exc}")


async def _on_stt_status(msg: Any) -> None:
    """Forward STT status changes to WebSocket clients."""
    try:
        data = json.loads(msg.data.decode())
        await manager.broadcast_message({"type": "stt_status", "payload": data})
    except Exception as exc:
        logger.warning(f"stt_status handler error: {exc}")


async def _on_global_log(msg: Any) -> None:
    """Central log handler: ring buffer + persist + fan-out to WebSocket clients."""
    try:
        data: dict[str, Any] = json.loads(msg.data.decode("utf-8"))
    except Exception:
        return

    # Ring buffer (always)
    _log_ring.append(data)

    # Fan-out to connected WebSocket clients
    for q in _log_subscribers:
        if q.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                q.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            q.put_nowait(data)

    # Persist if level matches
    level = data.get("level", "").upper()
    if level in _LOG_PERSIST_LEVELS and _lifespan_db_factory is not None:
        from datetime import UTC, datetime

        async with _lifespan_db_factory() as db:
            db.add(
                LogEntry(
                    timestamp=datetime.now(UTC).isoformat(),
                    service=data.get("service", "unknown"),
                    level=level,
                    message=str(data.get("message", "")),
                )
            )
            await db.commit()


async def _log_retention_loop(db_factory: Any, stop_event: asyncio.Event) -> None:
    """Purge old log entries daily based on LOG_RETENTION_DAYS."""
    while not stop_event.is_set():
        try:
            await asyncio.sleep(86400)  # Once per day
        except asyncio.CancelledError:
            return
        try:
            from datetime import UTC, datetime, timedelta

            cutoff = (datetime.now(UTC) - timedelta(days=_LOG_RETENTION_DAYS)).isoformat()
            async with db_factory() as db:
                from sqlalchemy import delete

                await db.execute(delete(LogEntry).where(LogEntry.timestamp < cutoff))
                await db.commit()
                logger.info("Log retention cleanup complete")
        except Exception as exc:
            logger.warning(f"Log retention cleanup failed: {exc}")


# Set during lifespan so module-level handlers can access it.
_lifespan_db_factory: Any = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifecycle manager: connect NATS, start background tasks, clean up."""
    global _lifespan_db_factory
    logger.info("API Gateway starting...")

    stop_event = asyncio.Event()
    pull_task: asyncio.Task[None] | None = None
    kv_watch_task: asyncio.Task[None] | None = None
    log_cleanup_task: asyncio.Task[None] | None = None

    # Initialize database
    db_engine, db_factory = await create_engine_and_tables()
    app.state.db_engine = db_engine
    app.state.db_factory = db_factory
    _lifespan_db_factory = db_factory
    logger.info("Database initialized")

    # JWT secret (ephemeral — tokens invalidated on restart)
    app.state.jwt_secret = secrets.token_hex(32)

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
        pull_task = asyncio.create_task(_pull_loop(sub, stop_event, db_factory))

        kv_watch_task = asyncio.create_task(_kv_connect_and_watch(app, js, stop_event))

        await nats_client.subscribe("system.session", cb=_on_session_event)
        await nats_client.subscribe("system.stt_status", cb=_on_stt_status)
        await nats_client.subscribe("transcript.interim.>", cb=_on_interim_transcript)

        # Global log subscription: ring buffer + persistent storage
        await nats_client.subscribe("logs.>", cb=_on_global_log)
        log_cleanup_task = asyncio.create_task(
            _log_retention_loop(db_factory, stop_event)
        )

        # session_kv / config_kv start as None; _kv_connect_and_watch updates them
        app.state.nats = nats_client
        app.state.js = js
        app.state.session_kv = None
        app.state.config_kv = None

        yield

    finally:
        logger.info("Shutting down... closing NATS connection.")
        stop_event.set()
        for task in (pull_task, kv_watch_task, log_cleanup_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        await nats_client.close()
        await db_engine.dispose()
        _lifespan_db_factory = None


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


@app.get("/display")
async def display() -> FileResponse:
    return FileResponse(_STATIC_DIR / "display.html")


@app.get("/admin")
async def admin() -> FileResponse:
    return FileResponse(_STATIC_DIR / "admin.html")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "api-gateway"}


_qr_cache: bytes | None = None


@app.get("/qr.png")
async def qr_code() -> Response:
    global _qr_cache
    if not SITE_URL:
        return JSONResponse(
            status_code=404,
            content={"error": "SITE_URL not configured"},
        )
    if _qr_cache is None:
        import io

        import qrcode  # type: ignore[import-untyped]

        img = qrcode.make(SITE_URL)
        buf = io.BytesIO()
        img.save(buf, format="PNG")  # pyright: ignore[reportCallIssue]
        _qr_cache = buf.getvalue()
    return Response(content=_qr_cache, media_type="image/png")


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
        except Exception:  # nosec B110
            pass  # Key absent or unreadable → no active session

    label = body.label if body else ""
    command = json.dumps({"command": "start", "label": label}).encode()
    js = request.app.state.js
    await js.publish("session.control", command)
    return JSONResponse(content={"status": "ok"})


class LoginBody(BaseModel):
    password: str


@app.post("/admin/auth")
async def admin_auth(request: Request, body: LoginBody) -> JSONResponse:
    """Verify password, return short-lived JWT."""
    if not verify_password(body.password):
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_password"},
        )
    token = create_token(request.app.state.jwt_secret)
    return JSONResponse(content={"token": token})


@app.post("/session/stop")
async def session_stop(
    request: Request, _: None = Depends(require_admin)
) -> JSONResponse:
    """Stop the active session. Requires admin JWT."""
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


# --- Admin endpoints ---


@app.get("/admin/status")
async def admin_status(request: Request) -> dict[str, Any]:
    """System status: service health, NATS streams, disk usage. No auth."""
    from api_gateway.status import get_system_status

    js = request.app.state.js
    return await get_system_status(js)


@app.get("/admin/sessions")
async def list_sessions(
    request: Request, _: None = Depends(require_admin)
) -> list[dict[str, Any]]:
    """List all recorded sessions with segment counts.

    Sessions with no stopped_at that aren't the current active session
    are orphaned (e.g. lost during a nuke/crash) and get closed
    automatically.
    """
    from sqlalchemy import func

    db_factory = request.app.state.db_factory
    async with db_factory() as db:
        # Close orphaned sessions (active in DB but not in NATS KV)
        orphan_stmt = (
            update(SessionModel)
            .where(
                SessionModel.stopped_at.is_(None),
                SessionModel.id != (_active_session_id or ""),
            )
            .values(stopped_at="interrupted")
        )
        await db.execute(orphan_stmt)
        await db.commit()

        stmt = (
            select(
                SessionModel,
                func.count(TranscriptSegment.id).label("segment_count"),
            )
            .outerjoin(
                TranscriptSegment,
                TranscriptSegment.session_id == SessionModel.id,
            )
            .group_by(SessionModel.id)
            .order_by(SessionModel.started_at.desc())
        )
        rows = (await db.execute(stmt)).all()

    return [
        {
            "id": s.id,
            "label": s.label,
            "started_at": s.started_at,
            "stopped_at": s.stopped_at,
            "segment_count": count,
        }
        for s, count in rows
    ]


@app.get("/admin/sessions/{session_id}")
async def get_session(
    request: Request, session_id: str, _: None = Depends(require_admin)
) -> JSONResponse:
    """Get session details with all transcript segments."""
    db_factory = request.app.state.db_factory
    async with db_factory() as db:
        result = await db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return JSONResponse(
                status_code=404,
                content={"error": "session_not_found"},
            )

        seg_result = await db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.session_id == session_id)
            .order_by(TranscriptSegment.id)
        )
        segments = list(seg_result.scalars().all())

    return JSONResponse(
        content={
            "session": {
                "id": session.id,
                "label": session.label,
                "started_at": session.started_at,
                "stopped_at": session.stopped_at,
            },
            "segments": [
                {
                    "id": seg.id,
                    "timestamp": seg.timestamp,
                    "speaker": seg.speaker,
                    "text": seg.text,
                    "confidence": seg.confidence,
                    "source": seg.source,
                }
                for seg in segments
            ],
        }
    )


@app.get("/admin/sessions/{session_id}/export")
async def export_session(
    request: Request,
    session_id: str,
    fmt: str = "txt",
    _: None = Depends(require_admin),
) -> Response:
    """Export a session transcript as plain text or PDF."""
    from api_gateway.export import generate_pdf, generate_txt

    db_factory = request.app.state.db_factory
    async with db_factory() as db:
        result = await db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return JSONResponse(
                status_code=404,
                content={"error": "session_not_found"},
            )

        seg_result = await db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.session_id == session_id)
            .order_by(TranscriptSegment.id)
        )
        segments = list(seg_result.scalars().all())

    filename = f"transcript-{session_id}"

    if fmt == "pdf":
        content = generate_pdf(session, segments)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": (f'attachment; filename="{filename}.pdf"')},
        )

    content_txt = generate_txt(session, segments)
    return Response(
        content=content_txt,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": (f'attachment; filename="{filename}.txt"')},
    )


class ScheduleBody(BaseModel):
    day_of_week: list[int]
    start_time: str
    stop_time: str
    label_template: str = ""
    stop_policy: str = "soft"
    enabled: bool = True


def _validate_schedule(body: ScheduleBody) -> str | None:
    """Return an error message if the schedule body is invalid."""
    if not body.day_of_week or not all(0 <= d <= 6 for d in body.day_of_week):
        return "day_of_week must contain values 0-6"
    import re

    if not re.match(r"^\d{2}:\d{2}$", body.start_time):
        return "start_time must be HH:MM"
    if not re.match(r"^\d{2}:\d{2}$", body.stop_time):
        return "stop_time must be HH:MM"
    valid_policies = {"hard", "soft"}
    if body.stop_policy not in valid_policies and not body.stop_policy.startswith(
        "grace_"
    ):
        return f"stop_policy must be one of {valid_policies} or grace_N"
    return None


@app.post("/admin/schedules")
async def create_schedule(
    request: Request, body: ScheduleBody, _: None = Depends(require_admin)
) -> JSONResponse:
    """Create a new recurring schedule."""
    import uuid

    err = _validate_schedule(body)
    if err:
        return JSONResponse(status_code=400, content={"error": err})

    schedule_id = uuid.uuid4().hex[:8]
    db_factory = request.app.state.db_factory
    async with db_factory() as db:
        row = Schedule(
            id=schedule_id,
            day_of_week=json.dumps(body.day_of_week),
            start_time=body.start_time,
            stop_time=body.stop_time,
            label_template=body.label_template,
            stop_policy=body.stop_policy,
            enabled=1 if body.enabled else 0,
        )
        db.add(row)
        await db.commit()

    return JSONResponse(status_code=201, content={"id": schedule_id})


@app.get("/admin/schedules")
async def list_schedules(
    request: Request,
) -> list[dict[str, Any]]:
    """List all recurring schedules."""
    db_factory = request.app.state.db_factory
    async with db_factory() as db:
        result = await db.execute(select(Schedule))
        rows = result.scalars().all()

    return [
        {
            "id": s.id,
            "day_of_week": json.loads(s.day_of_week),
            "start_time": s.start_time,
            "stop_time": s.stop_time,
            "label_template": s.label_template,
            "stop_policy": s.stop_policy,
            "enabled": bool(s.enabled),
        }
        for s in rows
    ]


@app.put("/admin/schedules/{schedule_id}")
async def update_schedule(
    request: Request,
    schedule_id: str,
    body: ScheduleBody,
    _: None = Depends(require_admin),
) -> JSONResponse:
    """Update an existing schedule."""
    err = _validate_schedule(body)
    if err:
        return JSONResponse(status_code=400, content={"error": err})

    db_factory = request.app.state.db_factory
    async with db_factory() as db:
        result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
        row = result.scalar_one_or_none()
        if row is None:
            return JSONResponse(
                status_code=404,
                content={"error": "schedule_not_found"},
            )

        await db.execute(
            update(Schedule)
            .where(Schedule.id == schedule_id)
            .values(
                day_of_week=json.dumps(body.day_of_week),
                start_time=body.start_time,
                stop_time=body.stop_time,
                label_template=body.label_template,
                stop_policy=body.stop_policy,
                enabled=1 if body.enabled else 0,
            )
        )
        await db.commit()

    return JSONResponse(content={"status": "ok"})


@app.delete("/admin/schedules/{schedule_id}")
async def delete_schedule(
    request: Request, schedule_id: str, _: None = Depends(require_admin)
) -> JSONResponse:
    """Delete a schedule."""
    from sqlalchemy import delete as sql_delete

    db_factory = request.app.state.db_factory
    async with db_factory() as db:
        result = await db.execute(sql_delete(Schedule).where(Schedule.id == schedule_id))
        await db.commit()

    if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
        return JSONResponse(
            status_code=404,
            content={"error": "schedule_not_found"},
        )
    return JSONResponse(content={"status": "ok"})


_DB_DIR = Path(os.getenv("DB_PATH", "/data/db/livestt.db")).parent
_LANCEDB_DIR = Path("/data/lancedb")


@app.post("/admin/backup")
async def create_backup(_: None = Depends(require_admin)) -> Response:
    """Create a tar.gz backup of /data/db/ and /data/lancedb/ (if present)."""
    import io
    import tarfile

    if not _DB_DIR.is_dir():
        return JSONResponse(
            status_code=404,
            content={"error": "No data directory found"},
        )

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for fpath in _DB_DIR.iterdir():
            if fpath.is_file():
                tar.add(str(fpath), arcname=f"db/{fpath.name}")
        if _LANCEDB_DIR.is_dir():
            for fpath in _LANCEDB_DIR.rglob("*"):
                if fpath.is_file():
                    arcname = f"lancedb/{fpath.relative_to(_LANCEDB_DIR)}"
                    tar.add(str(fpath), arcname=arcname)
    buf.seek(0)

    from datetime import UTC, datetime

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    filename = f"livestt-backup-{stamp}.tar.gz"

    return Response(
        content=buf.getvalue(),
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/admin/restore")
async def restore_backup(
    request: Request, _: None = Depends(require_admin)
) -> JSONResponse:
    """Restore a previously created backup archive.

    Accepts a tar.gz upload.  Files prefixed ``db/`` are extracted to
    /data/db/ and files prefixed ``lancedb/`` to /data/lancedb/.
    Legacy flat archives (no prefix) are treated as db files.
    """
    import io
    import tarfile

    body = await request.body()
    if not body:
        return JSONResponse(status_code=400, content={"error": "Empty request body"})

    try:
        with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tar:
            restored = _extract_backup(tar)
    except tarfile.TarError:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid tar.gz archive"},
        )

    return JSONResponse(content={"status": "ok", "restored_files": restored})


def _extract_backup(tar: Any) -> dict[str, int]:
    restored: dict[str, int] = {"db": 0, "lancedb": 0}
    for member in tar.getmembers():
        if member.isdir():
            continue
        # Security: reject absolute paths and path traversal
        if member.name.startswith("/") or ".." in member.name:
            continue
        if member.name.startswith("db/"):
            dest = _DB_DIR / member.name.removeprefix("db/")
        elif member.name.startswith("lancedb/"):
            dest = _LANCEDB_DIR / member.name.removeprefix("lancedb/")
        elif member.name.endswith((".db", ".db-wal", ".db-shm")):
            # Legacy flat format (pre-v0.14)
            dest = _DB_DIR / member.name
        else:
            continue
        bucket = "lancedb" if member.name.startswith("lancedb/") else "db"
        dest.parent.mkdir(parents=True, exist_ok=True)
        src = tar.extractfile(member)
        if src:
            dest.write_bytes(src.read())
            restored[bucket] += 1
    return restored


class SpeakerEnrollBody(BaseModel):
    name: str


@app.get("/admin/speakers")
async def list_speakers(_: None = Depends(require_admin)) -> dict[str, Any]:
    """List enrolled speakers. Returns an empty list until identifier is wired."""
    return {"speakers": []}


@app.post("/admin/speakers")
async def enroll_speaker(
    request: Request,
    body: SpeakerEnrollBody,
    _: None = Depends(require_admin),
) -> JSONResponse:
    """Queue a speaker enrollment command to the identifier service via NATS."""
    nc: NATS = request.app.state.nats
    payload = json.dumps({"command": "enroll", "name": body.name}).encode()
    await nc.publish("identifier.command", payload)
    return JSONResponse(content={"status": "queued"})


@app.delete("/admin/speakers/{name}")
async def delete_speaker(
    request: Request,
    name: str,
    _: None = Depends(require_admin),
) -> JSONResponse:
    """Queue a speaker delete command to the identifier service via NATS."""
    nc: NATS = request.app.state.nats
    payload = json.dumps({"command": "delete", "name": name}).encode()
    await nc.publish("identifier.command", payload)
    return JSONResponse(content={"status": "queued"})


@app.websocket("/admin/logs")
async def admin_logs_websocket(websocket: WebSocket) -> None:
    """Stream structured log messages from all services to an admin client.

    On connect, replays the in-memory ring buffer so the client sees
    recent history.  Then subscribes to ``_log_subscribers`` for live
    messages fed by the global ``_on_global_log`` handler.
    """
    await websocket.accept()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_LOG_WS_QUEUE_SIZE)
    _log_subscribers.append(queue)
    try:
        # Replay ring buffer
        for entry in list(_log_ring):
            await websocket.send_json({"type": "log", "payload": entry})

        # Live stream
        while True:
            log_payload = await queue.get()
            await websocket.send_json({"type": "log", "payload": log_payload})
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        _log_subscribers.remove(queue)


@app.get("/admin/logs/export")
async def export_logs(
    request: Request,
    level: str = "",
    service: str = "",
    limit: int = 1000,
    _: None = Depends(require_admin),
) -> Response:
    """Export persisted log entries as JSON lines.

    Query params: level (comma-separated), service, limit (default 1000).
    """
    from sqlalchemy import desc

    db_factory = request.app.state.db_factory
    stmt = select(LogEntry).order_by(desc(LogEntry.timestamp)).limit(limit)
    if level:
        levels = [lv.strip().upper() for lv in level.split(",")]
        stmt = stmt.where(LogEntry.level.in_(levels))
    if service:
        stmt = stmt.where(LogEntry.service == service)

    async with db_factory() as db:
        result = await db.execute(stmt)
        rows = result.scalars().all()

    lines = "\n".join(
        json.dumps(
            {
                "timestamp": r.timestamp,
                "service": r.service,
                "level": r.level,
                "message": r.message,
            }
        )
        for r in reversed(rows)
    )
    return Response(
        content=lines,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="livestt-logs.jsonl"'},
    )


async def _replay_session_transcript(websocket: WebSocket, session_id: str) -> None:
    """Send persisted transcript segments for the active session."""
    if _lifespan_db_factory is None:
        return
    try:
        async with _lifespan_db_factory() as db:
            result = await db.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.session_id == session_id)
                .order_by(TranscriptSegment.id)
            )
            segments = result.scalars().all()
            for seg in segments:
                await websocket.send_json(
                    {
                        "type": "transcript",
                        "payload": {
                            "text": seg.text,
                            "speaker": seg.speaker,
                            "is_final": True,
                            "confidence": seg.confidence,
                            "source": seg.source,
                            "timestamp": seg.timestamp,
                        },
                    }
                )
        await websocket.send_json(
            {"type": "replay_complete", "payload": {"session_id": session_id}}
        )
    except Exception as exc:
        logger.warning(f"Transcript replay failed: {exc}")


@app.websocket("/ws/transcripts")
async def websocket_endpoint(websocket: WebSocket) -> None:
    if len(manager.active_connections) >= MAX_WS_CONNECTIONS:
        logger.warning(
            "WebSocket connection rejected: limit reached (%d)",
            MAX_WS_CONNECTIONS,
        )
        await websocket.close(code=1013)
        return
    await manager.connect(websocket)
    logger.info("Client connected to WebSocket.")

    # Replay current session's transcript so the client catches up.
    if _active_session_id:
        await websocket.send_json(
            {"type": "replay_start", "payload": {"session_id": _active_session_id}}
        )
        await _replay_session_transcript(websocket, _active_session_id)

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
