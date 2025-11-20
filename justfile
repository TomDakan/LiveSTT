# live-stt - Task Runner

# --- Environment ---

# Bootstrap the local dev environment (secrets, data dirs).
setup:
    @python scripts/setup_dev.py

# --- Quality Assurance & Testing ---

# Check if code formatting is correct (Ruff).
format-check *args:
    @ruff format . --diff {{ just_args }}

# Apply code formatting (Ruff).
format *args:
    @ruff format . {{ just_args }}

# Run the linter and import sorter (Ruff).
lint *args:
    @ruff check . --fix {{ just_args }}

# Run static type checking (MyPy).
type-check *args:
    @mypy . {{ just_args }}

# Run the test suite (pytest).
test *args:
    @pytest {{ just_args }}

# Placeholder for deployment tasks.
deploy *args:
    @echo 'Deploying...' {{ just_args }}

# Check for known security vulnerabilities in dependencies.
safety-check *args:
    @safety check {{ just_args }}

# Run Bandit security linter.
bandit-check *args:
    @bandit -r services {{ just_args }}

# Export documentation dependencies for Read the Docs.
export-docs-reqs *args:
    @pdm export --group docs --without-hashes -o docs-requirements.txt {{ just_args }}

# Create a new Architecture Decision Record.
adr *args:
    @{{ _copier_python }} scripts/new_adr.py {{ just_args }}

# Run the full quality assurance suite.
qa:
    @just format-check
    @just lint
    @just type-check
    @just test
    @just safety-check
    @just bandit-check
