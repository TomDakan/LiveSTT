# services/identifier/Dockerfile

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY .docker-context/ ./

RUN uv sync --frozen --no-install-project --package identifier

FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# LanceDB database and WeSpeaker model directories
# /data/lancedb is expected to be a named volume (see docker-compose)
# /app/models/wespeaker.xml must be provided externally — see docs/20_architecture/adrs/0008-split-brain-architecture.md
RUN mkdir -p /data/lancedb models

COPY libs/messaging ./libs/messaging
COPY services/identifier ./services/identifier

ENV PYTHONPATH="/app/services/identifier/src:/app/libs/messaging/src:$PYTHONPATH"
CMD ["python", "-m", "identifier.main"]
