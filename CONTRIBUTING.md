# Contributing to Live STT

Thank you for considering contributing to this project! Please follow these guidelines.

---

## 1. Development Environment

### Prerequisites
- **OS**: Linux (Ubuntu 22.04+), macOS, or Windows (WSL2)
- **Tools**:
  - `mise` (for managing Python/Node versions)
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
   mise install  # Installs Python 3.11, PDM, etc.
   pdm install   # Installs Python packages
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

## 6. Code Style

- **Python**: Checked by `ruff` (PEP8 compliant) and `mypy` (strict typing).
- **Architecture**: Follows the [Microservices Pattern](docs/20_architecture/architecture_definition.md).
- **Secrets**: NEVER commit secrets. Use `.env` for local dev.
