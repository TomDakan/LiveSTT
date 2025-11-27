# Live STT

**Resilient, offline-first, real-time transcription appliance for church environments.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Status: Development](https://img.shields.io/badge/Status-Development-yellow)](https://github.com/yourusername/live-stt)

---

## 📖 Documentation

Full documentation is available in the `docs/` directory:

- **[Quickstart](docs/quickstart.md)**: Deploy in 10 minutes.
- **[Hardware Guide](docs/40_hardware/hbom.md)**: Industrial x86 (NUC N97) BOM.
- **[Architecture](docs/20_architecture/architecture_definition.md)**: Split-Brain design (Cloud Text + Edge Identity).
- **[API Reference](docs/api.md)**: REST and WebSocket API docs.

---

## 🌟 Features

- **Split-Brain Architecture**: Combines Cloud STT accuracy with Edge Biometric privacy.
- **Deepgram Nova-3**: Industry-leading transcription accuracy and speed.
- **Hybrid Tagging**: Zero-drift speaker identification using local biometrics.
- **Industrial Reliability**: Fanless x86 hardware with Power Loss Protection (PLP).
- **Offline-First**: "Black Box" loopback filesystem ensures zero data loss during outages.

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
- **Docker**: Required for NATS and LanceDB

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
# 1. Start Infrastructure (NATS + LanceDB)
docker compose up -d nats lancedb

# 2. Run Services (in separate terminals)
just start api-gateway
just start stt-provider
just start identity-manager
```

### Development Commands

We use [Just](https://github.com/casey/just) for common tasks:

```bash
just qa              # Run full QA suite (format, lint, type-check, test, security)
just format          # Auto-format code with Ruff
just type-check      # Run MyPy type checking
just test            # Run pytest
just nats-cli        # Open NATS CLI shell
just nats-spy        # Watch all NATS messages
```

### Project Structure

```
live-stt/
├── services/           # Microservices
│   ├── api-gateway/    # FastAPI REST + WebSocket server
│   ├── stt-provider/   # Deepgram STT integration
│   ├── identifier/     # OpenVINO Biometrics
│   └── identity-manager/ # Hybrid Tagging Logic
├── src/live_stt/       # Shared library code
├── docs/               # Architecture & Ops docs
├── justfile            # Task runner commands
└── pyproject.toml      # Monorepo config
```

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0**. See [LICENSE](LICENSE) for details.
