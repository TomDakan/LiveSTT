# live-stt - Task Runner

# --- Environment ---
# --- Cross-Platform Shell Config ---
# On Linux/Mac, use bash. On Windows, use PowerShell.
set shell := ["bash", "-c"]
set windows-shell := ["powershell.exe", "-NoProfile", "-Command"]

# Install dependencies (uv sync)
install:
    uv sync

# Add a dependency to a specific workspace member
# Usage: just add-dep api pandas
add-dep service package:
    uv add --package {{service}} {{package}}

# Clean up artifacts (cross-platform python script)
clean:
    #!/usr/bin/env -S uv run python
    import shutil
    import pathlib

    dirs = [".venv", "__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache", "dist", "build"]
    for d in dirs:
        p = pathlib.Path(d)
        if p.exists():
            print(f"Removing {p}")
            shutil.rmtree(p, ignore_errors=True)

    # Also clean recursively
    for p in pathlib.Path(".").rglob("__pycache__"):
        print(f"Removing {p}")
        shutil.rmtree(p, ignore_errors=True)

# --- Quality Assurance & Testing ---

# Check if code formatting is correct (Ruff).
format-check *args:
    uv run ruff format --diff {{ if args == "" { "." } else { args } }}

# Apply code formatting (Ruff).
format *args:
    uv run ruff format {{ if args == "" { "." } else { args } }}

# Run the linter and import sorter (Ruff).
lint *args:
    uv run ruff check --fix {{ if args == "" { "." } else { args } }}

# Run static type checking (MyPy).
type-check service="":
    uv run scripts/type_check.py {{ service }}

# Run the test suite (pytest). Skips integration tests by default.
test *args:
    uv run python -m pytest -m "not integration" {{ args }}

# Run tests for a specific service
test-service service *args:
    uv run python -m pytest services/{{service}} {{args}}

# Placeholder for deployment tasks.
deploy *args:
    echo 'Deploying...' {{ args }}

# Check for known security vulnerabilities in dependencies.
safety-scan *args:
    uv run python -m safety scan {{ args }}

# Run Bandit security linter.
bandit-check *args:
    uv run python -m bandit -c pyproject.toml -r services -x "tests,services/api-gateway/tests,services/audio-producer/tests,services/stt-provider/tests" {{ args }}

# Export documentation dependencies for Read the Docs.
export-docs-reqs *args:
    uv export --group docs --no-hashes -o docs-requirements.txt {{ args }}

# Start the stack in detached mode
up:
    docker compose up -d

# Force a rebuild of images and restart containers
up-build:
    docker compose up -d --build

# The "Nuclear Option": Stop containers and DELETE volumes
nuke:
    docker compose down --volumes --remove-orphans

# Stop the stack
down:
    docker compose down

# --- Observability ---

# Follow logs for all services
logs:
    docker compose logs -f

# Follow logs for a specific service
log service:
    docker compose logs -f {{ service }}

# --- Development ---

# Start a service locally
start service:
    @echo "Starting {{service}}..."
    uv run --package {{service}} python -m {{replace(service, "-", "_")}}.main

# Open a shell inside a container
shell service:
    docker compose exec -it {{ service }} /bin/bash

# Rebuild a SINGLE service without cache
rebuild-hard service:
    docker compose build --no-cache {{ service }}
    docker compose up -d --force-recreate {{ service }}

# Create a new Architecture Decision Record.
adr *args:
    uv run scripts/new_adr.py {{ args }}

# Interactive NATS debugging
nats-cli:
    docker run -it --network=host natsio/nats-box:latest

# View all messages (dev spy mode)
nats-spy:
    docker run --network=host natsio/nats-box:latest nats sub ">"

# Inspect specific subject
nats-tail subject="audio.raw":
    docker run --network=host natsio/nats-box:latest nats sub {{subject}}

# NATS health check
nats-health:
    docker run --network=host natsio/nats-box:latest nats server check

# Run the full quality assurance suite.
qa:
    just format-check
    just lint
    just type-check
    just test
    just safety-scan
    just bandit-check

qa-github:
    just format-check
    just lint
    just type-check
    just test
    just bandit-check
