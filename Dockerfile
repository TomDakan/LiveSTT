# === Stage 1: Builder ===
# Use the Python version selected by the user
FROM python:3.13-slim as builder
ENV PYTHONUNBUFFERED=1 \
PIP_DEFAULT_TIMEOUT=100
# Install PDM
RUN pip install --no-cache-dir pdm
WORKDIR /app
COPY pyproject.toml pdm.lock ./
# Install all dependencies (dev, prod, etc.)
RUN pdm install --prod --no-lock
RUN pdm install --no-lock
# === Stage 2: Development (Default Target) ===
# This is used for docker-compose.yml
FROM builder as development
WORKDIR /app
# Copy the rest of the project source
COPY . .
# This CMD is just a placeholder for the dev stage
CMD ["tail", "-f", "/dev/null"]
# === Stage 3: Production ===
# This is a lean, secure final image
FROM python:3.13-slim as production
ENV PYTHONUNBUFFERED=1
# Create a non-root user for security
RUN addgroup --system app && adduser --system --group app
WORKDIR /app
# Copy the virtual environment from the 'builder' stage
COPY --from=builder /app/.venv ./.venv
# Copy *only* the application source code
COPY ./src ./src
# Chown all files to the new user
RUN chown -R app:app /app
USER app
# Set the PATH to include the venv
ENV PATH="/app/.venv/bin:$PATH"


    # If not a CLI, default to a keep-alive command.
    # You should update this to run your actual application (e.g., a web server).
    CMD ["tail", "-f", "/dev/null"]

