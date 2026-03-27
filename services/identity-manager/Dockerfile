# services/identity-manager/Dockerfile

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY .docker-context/ ./

RUN uv sync --frozen --no-install-project --package identity-manager

FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

COPY libs/messaging ./libs/messaging
COPY services/identity-manager ./services/identity-manager

ENV PYTHONPATH="/app/services/identity-manager/src:/app/libs/messaging/src:$PYTHONPATH"
CMD ["python", "-m", "identity_manager.main"]
