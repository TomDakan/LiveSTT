# live-stt - Task Runner

# Use PowerShell on Windows, default to sh on Linux
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# --- Environment ---



# --- Quality Assurance & Testing ---

# Check if code formatting is correct (Ruff).
format-check *args:
    ruff format . --diff {{ args }}

# Apply code formatting (Ruff).
format *args:
    ruff format . {{ args }}

# Run the linter and import sorter (Ruff).
lint *args:
    ruff check . --fix {{ args }}

# Run static type checking (MyPy).
# Run static type checking (MyPy).
type-check service="":
    uv run scripts/type_check.py {{ service }}

# Run the test suite (pytest).
test *args:
    pytest {{ args }}

# Placeholder for deployment tasks.
deploy *args:
    echo 'Deploying...' {{ args }}

# Check for known security vulnerabilities in dependencies.
safety-check *args:
    safety check {{ args }}

# Run Bandit security linter.
bandit-check *args:
    bandit -r services {{ args }}

# Export documentation dependencies for Read the Docs.
export-docs-reqs *args:
    pdm export --group docs --without-hashes -o docs-requirements.txt {{ args }}

# Start the stack in detached mode
up:
    docker compose up -d

# Force a rebuild of images and restart containers (Use when code changes)
up-build:
    docker compose up -d --build

# The "Nuclear Option": Stop containers and DELETE volumes (Fixes stale PDM/venv issues)
nuke:
    docker compose down --volumes --remove-orphans

# Stop the stack
down:
    docker compose down

# --- Observability ---

# Follow logs for all services
logs:
    docker compose logs -f

# Follow logs for a specific service (Usage: just log stt-provider)
log service:
    docker compose logs -f {{ service }}

# --- Development ---

# Open a shell inside a container (Usage: just shell api-gateway)
shell service:
    docker compose exec -it {{ service }} /bin/bash

# Rebuild a SINGLE service without cache (Fixes stubborn dependency issues)
# Usage: just rebuild-hard stt-provider
rebuild-hard service:
    docker compose build --no-cache {{ service }}
    docker compose up -d --force-recreate {{ service }}

# Create a new Architecture Decision Record.
adr *args:
    uv run scripts/new_adr.py {{ args }}

# Run the full quality assurance suite.
qa:
    just format-check
    just lint
    just type-check
    just test
    just safety-check
    just bandit-check
