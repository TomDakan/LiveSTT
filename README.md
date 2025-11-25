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

## 🚀 Quick Start (Local Dev)

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

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to set up your development environment and submit pull requests.

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0**. See [LICENSE](LICENSE) for details.
