# services/audio-producer/Dockerfile

FROM python:3.12-slim as builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy scaffolded Docker build context (created by scripts/scaffold_context.py)
# This includes: uv.lock, pyproject.toml, and all service/lib pyproject.toml files
COPY .docker-context/ ./

# Install build dependencies
RUN apt-get update && apt-get install -y \
    libasound2-dev \
    portaudio19-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Sync dependencies
RUN uv sync --frozen --no-install-project --package audio-producer

FROM python:3.12-slim
WORKDIR /app

# Install system dependencies for PyAudio/ALSA
RUN apt-get update && apt-get install -y \
    libasound2-dev \
    portaudio19-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy venv
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Copy shared libs
COPY libs/messaging ./libs/messaging

# Copy service code
COPY services/audio-producer ./services/audio-producer

# Install project
# RUN uv sync --frozen --package audio-producer

ENV PYTHONPATH="/app/services/audio-producer/src:/app/libs/messaging/src:$PYTHONPATH"
CMD ["python", "-m", "audio_producer.main"]
