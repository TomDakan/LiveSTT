# services/stt-provider/Dockerfile

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY .docker-context/ ./

RUN uv sync --frozen --no-install-project --package stt-provider

FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

COPY libs/messaging ./libs/messaging
COPY services/stt-provider ./services/stt-provider

ENV PYTHONPATH="/app/services/stt-provider/src:/app/libs/messaging/src:$PYTHONPATH"
CMD ["python", "-m", "stt_provider.main"]
