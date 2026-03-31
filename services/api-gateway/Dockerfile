# services/api-gateway/Dockerfile

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY .docker-context/ ./

RUN uv sync --frozen --no-install-project --package api-gateway

FROM python:3.12-slim AS tailwind-builder
WORKDIR /app

COPY services/api-gateway/src/api_gateway/static/index.html \
     services/api-gateway/src/api_gateway/static/display.html \
     /app/services/api-gateway/src/api_gateway/static/

# Tailwind v4 input CSS: @import triggers utility class scanning
RUN printf '@import "tailwindcss";\n' > /app/input.css

# Download Tailwind v4 standalone CLI and generate CSS
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sLo /tmp/tailwindcss \
         https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    && chmod +x /tmp/tailwindcss \
    && /tmp/tailwindcss \
         --input /app/input.css \
         --output /app/services/api-gateway/src/api_gateway/static/tailwind.css \
         --minify

FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

COPY libs/messaging ./libs/messaging
COPY services/api-gateway ./services/api-gateway
COPY --from=tailwind-builder \
     /app/services/api-gateway/src/api_gateway/static/tailwind.css \
     /app/services/api-gateway/src/api_gateway/static/tailwind.css

ENV PYTHONPATH="/app/services/api-gateway/src:/app/libs/messaging/src:$PYTHONPATH"
CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
