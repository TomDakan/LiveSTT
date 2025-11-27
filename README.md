# Live STT

**Resilient, offline-first, real-time transcription appliance for church environments.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Status: Development](https://img.shields.io/badge/Status-Development-yellow)](https://github.com/yourusername/live-stt)

---

## 📖 Documentation

Full documentation is available in the `docs/` directory:

- **[Quickstart](docs/quickstart.md)**: Deploy in 10 minutes.
- **[Hardware Guide](docs/40_hardware/hbom.md)**: Recommended hardware (Jetson Orin Nano).
- **[Architecture](docs/20_architecture/architecture_definition.md)**: System design and microservices.
- **[API Reference](docs/api.md)**: REST and WebSocket API docs.

---

## 🌟 Features

- **Offline-First**: Works without internet (buffers audio until connection restores).
- **Real-Time**: Low latency (<500ms) transcription using Deepgram.
- **Speaker ID**: Identifies known speakers (e.g., "Pastor Mike") using local biometrics.
- **Resilient**: Auto-recovers from power loss and network outages.
- **Privacy-Focused**: Voiceprints stored locally and encrypted.

---

## 🚀 Quick Start (Docker)

1. **Clone & Setup**:
   ```bash
   git clone https://github.com/yourusername/live-stt.git
   cd live-stt
   cp .env.example .env
   # Add your DEEPGRAM_API_KEY to .env
   ```

2. **Run**:
   ```bash
   docker compose up
   ```

3. **Access**:
   - Web UI: `http://localhost:8000`
   - API Docs: `http://localhost:8000/docs`

---

## 💻 Local Development Setup

### Prerequisites

- **Python**: 3.10+ (tested on 3.12-3.13)
- **Package Manager**: [pdm](https://pdm-project.org/) (uses uv as backend)
- **Task Runner**: [just](https://github.com/casey/just) (optional but recommended)
- **Docker** (optional, for containerized testing)

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/live-stt.git
   cd live-stt
   ```

2. **Install dependencies**:
   ```bash
   pdm install
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your DEEPGRAM_API_KEY
   ```

### Running Services

This is a **monorepo** with multiple microservices. Run individual services for development:

```bash
# Run the API Gateway (REST + WebSocket)
just start api-gateway

# Run the STT Provider (Deepgram integration)
just start stt-provider

# Run the Message Broker (ZMQ proxy)
just start broker
```

Or run all services via Docker Compose:
```bash
docker compose up
```

### Development Commands

We use [Just](https://github.com/casey/just) for common tasks:

```bash
just qa              # Run full QA suite (format, lint, type-check, test, security)
just format          # Auto-format code with Ruff
just format-check    # Check formatting (CI-safe)
just lint            # Run linter (auto-fix)
just type-check      # Run MyPy type checking
just test            # Run pytest
just bandit-check    # Security scan with Bandit
```

### Testing

Run the test suite:
```bash
# All tests
pytest

# With coverage report
pytest --cov

# Specific test file
pytest tests/test_settings.py
```

### Project Structure

```
live-stt/
├── services/           # Microservices (each with own src, tests, deps)
│   ├── api-gateway/   # FastAPI REST + WebSocket server
│   ├── broker/        # ZMQ message broker (XSUB/XPUB)
│   ├── stt-provider/  # Deepgram STT integration
│   └── ...
├── src/live_stt/      # Shared library code
├── scripts/           # Utility scripts
├── tests/             # Root-level tests
├── justfile           # Task runner commands
└── pyproject.toml     # Monorepo config (PDM workspace)

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to set up your development environment and submit pull requests.

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0**. See [LICENSE](LICENSE) for details.
