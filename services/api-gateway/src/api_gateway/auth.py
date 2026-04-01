"""Admin authentication: bcrypt password verification + JWT tokens."""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import HTTPException, Request

logger = logging.getLogger("api-gateway")

ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
ADMIN_TOKEN_TTL_S = int(os.getenv("ADMIN_TOKEN_TTL_S", "3600"))


def verify_password(plain: str) -> bool:
    """Check plain password against ADMIN_PASSWORD_HASH env var."""
    if not ADMIN_PASSWORD_HASH:
        logger.warning("ADMIN_PASSWORD_HASH not set — accepting any password (dev mode)")
        return True
    return bcrypt.checkpw(
        plain.encode("utf-8"),
        ADMIN_PASSWORD_HASH.encode("utf-8"),
    )


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
