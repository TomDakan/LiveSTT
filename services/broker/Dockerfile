# services/broker/Dockerfile

FROM ghcr.io/astral-sh/uv:latest as builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy root workspace config
COPY pyproject.toml uv.lock ./
# Copy service config
COPY services/broker/pyproject.toml ./services/broker/pyproject.toml

# Sync dependencies
RUN uv sync --frozen --no-install-project --package broker

FROM python:3.12-slim
WORKDIR /app

# Copy venv
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy service code
COPY services/broker ./services/broker
# Copy root src if needed
COPY src ./src

# Install project
RUN uv sync --frozen --package broker

CMD ["uv", "run", "python", "-u", "services/broker/src/main.py"]
