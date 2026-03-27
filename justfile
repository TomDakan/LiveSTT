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

# E2E smoke test: file audio → NATS → Deepgram → identity-manager → WebSocket.
# Requires: DEEPGRAM_API_KEY in .env, Docker running.
# Containers are left running after the test so you can inspect logs with: just logs
e2e: scaffold
    $env:AUDIO_FILE = "/data/test_speaker_30s.wav"; docker compose -f docker-compose.yml -f docker-compose.file-test.yml up -d --build nats api-gateway stt-provider identity-manager audio-producer
    uv run python -m pytest tests/integration/test_e2e_container.py -v -s -m integration

# Placeholder for deployment tasks.
deploy *args:
    echo 'Deploying...' {{ args }}

# Check for known security vulnerabilities in dependencies.
safety-scan *args:
    uv run python -m safety scan {{ args }}

# Run Bandit security linter.
bandit-check *args:
    uv run python -m bandit -c pyproject.toml -r . {{ args }}

# Export documentation dependencies for Read the Docs.
export-docs-reqs *args:
    uv export --group docs --no-hashes -o docs-requirements.txt {{ args }}

# Scaffold Docker build context (required for build)
scaffold:
    uv run python scripts/scaffold_context.py
    uv run python scripts/generate_dockerignore.py

# Start the stack in detached mode
up: scaffold
    docker compose up -d

# Force a rebuild of images and restart containers
up-build: scaffold
    docker compose up -d --build

# Start audio-producer + NATS using a WAV file instead of live mic.
# Strips the /dev/snd device mount so it works without ALSA/USB hardware.
# Usage: just file-test tests/data/test_speaker.wav
file-test wav_file="tests/data/test_speaker.wav": scaffold
    $env:AUDIO_FILE = "/data/{{file_name(wav_file)}}"; docker compose -f docker-compose.yml -f docker-compose.file-test.yml up -d nats audio-producer

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

# --- USB/ALSA Passthrough (Windows dev environment) ---

# Wake WSL2 (if idle) and attach the RME Babyface Pro to WSL2 for ALSA passthrough.
# Discovers the bus ID dynamically — safe across reboots.
# Run this before `just up` when using live mic input.
attach-usb:
    #!/usr/bin/env pwsh
    $busid = (usbipd list | Select-String "Babyface" | ForEach-Object { ($_ -split '\s+')[0] } | Select-Object -First 1)
    if (-not $busid) { Write-Error "RME Babyface Pro not found. Check USB connection."; exit 1 }
    Write-Host "Waking WSL2..."
    wsl echo "WSL2 ready"
    Write-Host "Attaching RME Babyface Pro (busid $busid) to WSL2..."
    usbipd attach --wsl --busid $busid
    Write-Host "Done! Run 'just up' to start the stack."

# Detach the RME Babyface Pro from WSL2 (returns audio control to Windows).
detach-usb:
    #!/usr/bin/env pwsh
    $busid = (usbipd list | Select-String "Babyface" | ForEach-Object { ($_ -split '\s+')[0] } | Select-Object -First 1)
    if (-not $busid) { Write-Error "RME Babyface Pro not found."; exit 1 }
    usbipd detach --busid $busid
    Write-Host "RME Babyface Pro detached."

# Run the full quality assurance suite.
qa:
    just format-check
    just lint
    just type-check
    just test
    just safety-scan
    just bandit-check
