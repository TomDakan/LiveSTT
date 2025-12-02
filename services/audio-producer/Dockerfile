# services/audio-producer/Dockerfile

# services/audio-producer/Dockerfile

FROM python:3.12-slim as builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy root workspace config
COPY pyproject.toml uv.lock ./
# Copy service config
COPY services/audio-producer/pyproject.toml ./services/audio-producer/pyproject.toml
# Copy shared libs config
COPY libs/messaging/pyproject.toml ./libs/messaging/pyproject.toml

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
