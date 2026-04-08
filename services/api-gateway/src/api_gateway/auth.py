"""Admin authentication: bcrypt password verification + JWT tokens."""

import collections
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import HTTPException, Request
from sqlalchemy import select

logger = logging.getLogger("api-gateway")

ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
ADMIN_TOKEN_TTL_S = int(os.getenv("ADMIN_TOKEN_TTL_S", "3600"))
MIN_PASSWORD_LENGTH = 8

# --- Rate limiting for /admin/auth ---
_AUTH_MAX_ATTEMPTS = 5
_AUTH_WINDOW_S = 60
_auth_attempts: dict[str, collections.deque[float]] = {}


def check_auth_rate_limit(client_ip: str) -> None:
    """Raise 429 if the IP has exceeded auth attempt limits."""
    now = time.monotonic()
    attempts = _auth_attempts.get(client_ip)
    if attempts is None:
        attempts = collections.deque()
        _auth_attempts[client_ip] = attempts
    # Evict old entries
    while attempts and attempts[0] < now - _AUTH_WINDOW_S:
        attempts.popleft()
    if len(attempts) >= _AUTH_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="too_many_attempts",
        )
    attempts.append(now)


async def _get_db_password_hash(db_factory: Any) -> str:
    """Read admin_password_hash from app_config table."""
    from api_gateway.db import AppConfig

    try:
        async with db_factory() as db:
            result = await db.execute(
                select(AppConfig.value).where(AppConfig.key == "admin_password_hash")
            )
            row = result.scalar_one_or_none()
            return row or ""
    except Exception:
        return ""


async def verify_password(plain: str, db_factory: Any = None) -> bool:
    """Check plain password against DB config, then env var fallback."""
    # Try DB first
    if db_factory is not None:
        db_hash = await _get_db_password_hash(db_factory)
        if db_hash:
            return bcrypt.checkpw(
                plain.encode("utf-8"),
                db_hash.encode("utf-8"),
            )

    # Fall back to env var
    if ADMIN_PASSWORD_HASH:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            ADMIN_PASSWORD_HASH.encode("utf-8"),
        )

    # No password configured — dev mode
    logger.warning("No admin password configured — accepting any password (dev mode)")
    return True


async def needs_setup(db_factory: Any = None) -> bool:
    """Return True if no admin password is configured anywhere."""
    if ADMIN_PASSWORD_HASH:
        return False
    if db_factory is not None:
        db_hash = await _get_db_password_hash(db_factory)
        if db_hash:
            return False
    return True


def create_token(secret: str) -> str:
    """Issue a short-lived JWT."""
    payload = {
        "exp": datetime.now(UTC) + timedelta(seconds=ADMIN_TOKEN_TTL_S),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    result: dict[str, Any] = jwt.decode(token, secret, algorithms=["HS256"])
    return result


async def require_admin(request: Request) -> None:
    """FastAPI dependency — validates Bearer JWT on the request."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing_token")
    try:
        decode_token(token, request.app.state.jwt_secret)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid_token") from exc
