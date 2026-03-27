# services/audio-classifier/Dockerfile

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY .docker-context/ ./

RUN uv sync --frozen --no-install-project --package audio-classifier

FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Download Silero VAD ONNX model (pinned to v5.1, ~2MB)
RUN mkdir -p models \
    && python -c "\
import urllib.request; \
urllib.request.urlretrieve( \
    'https://github.com/snakers4/silero-vad/raw/v5.1/src/silero_vad/data/silero_vad.onnx', \
    'models/silero_vad.onnx' \
)"

COPY libs/messaging ./libs/messaging
COPY services/audio-classifier ./services/audio-classifier

ENV PYTHONPATH="/app/services/audio-classifier/src:/app/libs/messaging/src:$PYTHONPATH"
CMD ["python", "-m", "audio_classifier.main"]
