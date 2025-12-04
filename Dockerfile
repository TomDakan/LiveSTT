# === Stage 1: Builder ===
FROM ghcr.io/astral-sh/uv:latest as builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy scaffolded Docker build context (created by scripts/scaffold_context.py)
# This includes: uv.lock, pyproject.toml, and all service/lib pyproject.toml files
COPY .docker-context/ ./

# Install dependencies
# Use --frozen to ensure lockfile is respected
# Use --no-install-project to only install dependencies first (caching)
RUN uv sync --frozen --no-install-project

# === Stage 2: Development (Default Target) ===
FROM python:3.12-slim as development
WORKDIR /app

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy project source
COPY . .

# Install the project itself
RUN uv sync --frozen

CMD ["tail", "-f", "/dev/null"]

# === Stage 3: Production ===
FROM python:3.12-slim as production
ENV PYTHONUNBUFFERED=1

RUN addgroup --system app && adduser --system --group app
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY ./src ./src
# Copy other necessary files if needed

RUN chown -R app:app /app
USER app
ENV PATH="/app/.venv/bin:$PATH"

CMD ["tail", "-f", "/dev/null"]
