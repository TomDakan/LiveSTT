# Contributing to Live STT

Thank you for considering contributing to this project! Please follow these guidelines.

---

## 1. Development Environment

### Prerequisites
- **OS**: Linux (Ubuntu 22.04+), macOS, or Windows (WSL2)
  > **Note**: The `audio-producer` service relies on ALSA and is fully functional only on Linux. On Windows/macOS, it will install without `pyalsaaudio` and must be run with the Mock audio source.
- **Tools**:
  - `mise` (for managing tools)
  - `docker` & `docker compose`
  - `just` (command runner)

### Setup
1. **Fork & Clone**:
   ```bash
   git clone https://github.com/yourusername/live-stt.git
   cd live-stt
   ```

2. **Install Dependencies**:
   ```bash
   mise install  # Installs uv, just, jq
   just install  # Syncs workspace dependencies via uv
   ```

3. **Environment Config**:
   ```bash
   cp .env.example .env
   # Edit .env to add DEEPGRAM_API_KEY (required for STT)
   ```

---

## 2. Hardware Tiers

This project supports three hardware tiers. Choose the one that matches your setup:

| Tier | Hardware | Docker Profile | Use Case |
|------|----------|----------------|----------|
| **Tier 1** | Industrial NUC (N97) | `gpu` | Production, OpenVINO Inference |
| **Tier 2** | Desktop w/ NVIDIA GPU | `gpu` | Full feature dev (w/ Speaker ID) |
| **Tier 3** | CPU-only (Laptop/CI) | `cpu` (default) | Core logic, UI, API dev |

**To run with GPU support (Tier 1/2)**:
```bash
export COMPOSE_PROFILES=gpu
just up
```

---

## 3. Common Commands (`just`)

We use `just` to automate common tasks:

- `just up`: Start services (Docker Compose)
- `just down`: Stop services
- `just logs`: Tail logs
- `just nats-spy`: Monitor NATS message bus
- `just nats-cli`: Interactive NATS shell
- `just test`: Run unit tests
- `just lint`: Run ruff and mypy
- `just format`: Auto-format code

---

## 4. Documentation

We follow a **Docs-as-Code** approach. Documentation lives in `docs/` and is versioned with the code.

- **Architecture**: `docs/20_architecture/` (ADRs, diagrams)
- **Requirements**: `docs/10_requirements/` (PRD)
- **API**: `docs/api.md`

**Rule**: If you change code behavior, you **MUST** update the corresponding documentation.

---

## 5. Pull Request Process

1. **Branching**: Use descriptive names (e.g., `feat/speaker-id`, `fix/websocket-reconnect`).
2. **Commits**: Follow [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat: add voiceprint enrollment`).
3. **Tests**: Ensure `just test` passes.
4. **Linting**: Ensure `just lint` passes.
5. **Review**: Submit PR and request review from maintainers.

---

## 6. Branching & Merging Strategy

This project uses **Conventional Commits** and **automated version bumping** via GitHub Actions. Follow these guidelines carefully to ensure the CI/CD pipeline works correctly.

### Branch Naming Convention
Use the format: `type/scope/description`

**Examples**:
- `feat/api/add-login` - Adding login feature to API
- `fix/stt/reconnect` - Fixing reconnection logic in STT provider
- `docs/architecture/update-diagrams` - Updating architecture diagrams
- `refactor/audio/simplify-pipeline` - Refactoring audio pipeline

**Common types**: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`

### Merge Strategy: Always Squash & Merge

When merging a PR into `main`, **always use "Squash and Merge"**. This is critical because:

1. **Single Commit Per PR**: Each feature/fix becomes a single commit on `main`
2. **Version Bump Trigger**: The squash commit message drives the automated version bump
3. **Clean History**: Keeps `main` branch history clean and readable

### The Squash Commit Message MUST Be a Valid Conventional Commit

When squashing, GitHub will prompt you for a commit message. This message **MUST** follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Examples**:
- `feat(api): add user authentication endpoint`
- `fix(stt): resolve Deepgram reconnection timeout`
- `docs: update deployment guide with Balena instructions`
- `perf(audio): optimize buffer allocation`

**Version Bump Mapping**:
- `feat:` → Minor version bump (0.1.0 → 0.2.0)
- `fix:`, `perf:`, `docs:` → Patch version bump (0.1.0 → 0.1.1)
- `BREAKING CHANGE:` in footer → Major version bump (0.1.0 → 1.0.0)

### The Golden Rule: Never Manually Bump Versions

**Do not manually edit version numbers** in `pyproject.toml` files while working on a feature branch. The CI pipeline automatically bumps versions when PRs are merged to `main`.

**Workflow**:
1. Create feature branch: `feat/my-feature`
2. Make changes (don't touch version numbers)
3. Open PR
4. **After PR is approved**: Use "Squash and Merge" with proper Conventional Commit message
5. **CI automatically**: Runs QA → Bumps version → Updates CHANGELOG.md → Commits & tags

---

## 7. Dependency Workflow

This monorepo uses **workspace dependencies** managed by `uv`. Internal libraries are versioned together with services using **Lock-Step Versioning**.

### Default State: Lock-Step Versioning

By default, all services and libraries share the same version number. Services depend on internal libraries using `workspace = true`:

```toml
# services/api-gateway/pyproject.toml
[project]
name = "api-gateway"
version = "0.1.0"  # Matches root version

[project.dependencies]
messaging = { workspace = true }  # Uses version from workspace
```

**When version bumps**: All `pyproject.toml` files listed in the root's `tool.commitizen.version_files` are updated together.

### Pinning State: When to "Eject" a Service

If you need a service to use a **specific older version** of an internal library (rare), you can "pin" it:

```toml
# services/legacy-api/pyproject.toml
[project.dependencies]
messaging = "==0.5.0"  # Pinned to specific version (not workspace)
```

**Use cases**:
- Gradual migration from old API to new API
- A/B testing different library versions
- Hot-fixing a service without upgrading dependencies

### New Service Protocol

When adding a new service (e.g., `services/new-app`):

1. **Create service** with `pyproject.toml`
2. **Set initial version** to match the current root version:
   ```toml
   [project]
   name = "new-app"
   version = "0.3.5"  # Match root version
   ```
3. **Add to version_files** in root `pyproject.toml`:
   ```toml
   [tool.commitizen]
   version_files = [
       "pyproject.toml:version",
       # ... other services ...
       "services/new-app/pyproject.toml:version",  # Add this line
   ]
   ```
4. **Use `workspace = true`** for internal dependencies

---

## 8. Code Style

- **Python**: Checked by `ruff` (PEP8 compliant) and `mypy` (strict typing).
- **Architecture**: Follows the [Microservices Pattern](docs/20_architecture/architecture_definition.md).
- **Secrets**: NEVER commit secrets. Use `.env` for local dev.
