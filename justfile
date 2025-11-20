# live-stt - Task Runner

# Use PowerShell on Windows, default to sh on Linux
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# --- Environment ---

# Bootstrap the local dev environment (secrets, data dirs).
setup:
    @python scripts/setup_dev.py

# --- Quality Assurance & Testing ---

# Check if code formatting is correct (Ruff).
format-check *args:
    @ruff format . --diff {{ args }}

# Apply code formatting (Ruff).
format *args:
    @ruff format . {{ args }}

# Run the linter and import sorter (Ruff).
lint *args:
    @ruff check . --fix {{ args }}

# Run static type checking (MyPy).
type-check *args:
    @mypy . {{ args }}

# Run the test suite (pytest).
test *args:
    @pytest {{ args }}

# Placeholder for deployment tasks.
deploy *args:
    @echo 'Deploying...' {{ args }}

# Check for known security vulnerabilities in dependencies.
safety-check *args:
    @safety check {{ args }}

# Run Bandit security linter.
bandit-check *args:
    @bandit -r services {{ args }}

# Export documentation dependencies for Read the Docs.
export-docs-reqs *args:
    @pdm export --group docs --without-hashes -o docs-requirements.txt {{ args }}

# --- Development ---
# Build the docker images.
build:
    @docker compose up -d --build
# Run the docker containers.
up:
    @docker compose up -d
# Stop the docker containers.
down:
    @docker compose down

# Create a new Architecture Decision Record.
adr *args:
    @python scripts/new_adr.py {{ args }}

# Run the full quality assurance suite.
qa:
    @just format-check
    @just lint
    @just type-check
    @just test
    @just safety-check
    @just bandit-check
