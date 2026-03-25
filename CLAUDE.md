# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Live STT** is a real-time speech-to-text appliance designed for live event environments including church services and lectures. It uses a **Split-Brain architecture**: cloud transcription (Deepgram Nova-3) runs in parallel with local biometric speaker identification (OpenVINO WeSpeaker). Designed for resilience against brief internet interruptions — audio is buffered locally so transcription can recover without gaps, but cloud STT (Deepgram) is required. Fully offline STT via a local model is a potential future addition. Runs on industrial x86 hardware (ASRock NUC N97).

## Commands

### Setup
```bash
just install          # uv sync — installs all workspace dependencies
```

### Testing
```bash
just test                         # Run unit tests (excludes integration tests)
just test-service audio-producer  # Test a specific service
```
Pytest markers: `unit`, `integration`, `slow`, `network`. Integration tests are skipped by default (require external resources).

### Linting & Type Checking
```bash
just format-check     # Check formatting (Ruff)
just format           # Apply formatting
just lint             # Fix imports + lint (Ruff)
just type-check       # MyPy strict mode
just bandit-check     # Security linting
just safety-scan      # Vulnerability scan
just qa               # Full suite: format, lint, type-check, test, security
```

### Docker
```bash
just scaffold         # Regenerate .docker-context/ (must run before up if services changed)
just up               # docker compose up -d (auto-scaffolds)
just up-build         # Force rebuild all images
just down             # Stop services
just nuke             # Delete all volumes (destructive)
```

### Local Development (without Docker)
```bash
docker compose up -d nats        # Start only NATS broker
just start api-gateway            # Run a single service locally
just shell api-gateway            # Shell into a running container
just logs                         # Tail all service logs
just log stt-provider             # Tail a specific service
```

### NATS Debugging
```bash
just nats-spy                     # Watch all NATS messages in real-time
just nats-tail audio.live         # Watch a specific subject
just nats-cli                     # Interactive NATS shell
just nats-health                  # Server health check
```

### Hardware (Windows WSL2 with RME Babyface Pro) #This may not end up being used due to WSL2 lack of audio drivers
```bash
just attach-usb       # Attach USB audio device to WSL2
just detach-usb       # Return audio to Windows
```

## Architecture

### Microservices (under `services/`)

| Service | Purpose | Status |
|---------|---------|--------|
| **audio-producer** | Captures audio from mic (ALSA/PyAudio) or file → publishes to NATS | Active |
| **stt-provider** | Streams audio to Deepgram → publishes raw transcripts | Active |
| **api-gateway** | FastAPI REST + WebSocket server (port 8000) | Active |
| **audio-classifier** | VAD (Voice Activity Detection) via OpenVINO | Stub |
| **identifier** | Speaker biometrics via WeSpeaker/OpenVINO + LanceDB | Stub |
| **identity-manager** | "Time Zipper" — fuses raw transcripts + speaker IDs | Stub |
| **health-watchdog** | Monitors service heartbeats via NATS KV | Stub |
| **data-sweeper** | 7-day transcript retention/cleanup | Stub |

### Message Bus (NATS JetStream)

All services communicate exclusively through NATS. Subject hierarchy:

```
preroll.audio            → pre-roll ring buffer (IDLE state, ~10 min audio in memory)
audio.live.<session_id>  → live audio chunks (ACTIVE recording)
audio.backfill           → offline backfill audio
transcript.raw.live      → Deepgram output (live)
transcript.raw.backfill  → Deepgram output (backfill)
transcript.identity.>    → speaker ID results (future)
transcript.final.>       → fused transcript + identity (future, consumed by api-gateway)
```

**Stream definitions** are in [libs/messaging/src/messaging/streams.py](libs/messaging/src/messaging/streams.py):
- `PRE_BUFFER`: Memory-based, 64MB, ~10 min audio pre-roll
- `AUDIO_STREAM`: File-based, 1-hour safety net
- `TRANSCRIPTION_STREAM`: File-based, 7-day retention
- `CLASSIFICATION_STREAM`: Memory-based VAD results

### Shared Library: `libs/messaging`

Every service extends **`BaseService`** ([libs/messaging/src/messaging/service.py](libs/messaging/src/messaging/service.py)), which handles:
- NATS connection lifecycle
- Signal handlers (graceful shutdown)
- Heartbeat loop (for health-watchdog)
- `run_business_logic(js, stop_event)` — override this in each service

**`NatsJSManager`** ([libs/messaging/src/messaging/nats.py](libs/messaging/src/messaging/nats.py)) provides idempotent stream creation via `ensure_stream()`.

### Data Flow

```
Mic/File
   └─→ audio-producer → [audio.live.<sid>] → stt-provider → [transcript.raw.live]
                      ↘ [preroll.audio]                                    ↓
                      ↘ [audio.backfill] → stt-provider → [transcript.raw.backfill]
                                                                           ↓
                                                              identity-manager (stub)
                                                                           ↓
                                                              [transcript.final.>]
                                                                           ↓
                                                                     api-gateway
                                                                     WebSocket → Browser
```

### Platform Tiers (ADR-0007)
- **Tier 1** (Target): ASRock NUC N97 — Full OpenVINO, ALSA, Power Loss Protection
- **Tier 2**: Desktop with NVIDIA GPU — GPU inference
- **Tier 3**: Laptop/CI — CPU only, no biometrics, PyAudio or file source

## Repo Layout

```
services/        # 8 microservices (each a uv workspace member)
libs/messaging/  # Shared NATS abstractions (BaseService, NatsJSManager, stream configs)
scripts/         # Build utilities (scaffold_context.py, generate_dockerignore.py, etc.)
docs/            # Comprehensive architecture docs, ADRs, runbooks
  20_architecture/  # C4 model, system_design_v8.0.md, 13 ADRs
  60_ops/           # Deployment, runbooks, NATS tooling
.docker-context/ # Auto-generated Docker build context (from scripts/scaffold_context.py)
```

## Key Conventions

### Branching & Commits
- Branch names: `feat/scope/description` or `fix/scope/description`
- compeleted branches are rebased and merged to main via github pull request
- Conventional commits drive automatic semantic versioning — **never manually edit version numbers**
- `feat:` → minor bump, `fix:` → patch bump, `BREAKING CHANGE:` → major bump. Github is currently configured to keep the version number at 0.X.X until we complete feature development.

### Code Style
- **Ruff**: line-length=90, double quotes, target py312
- **MyPy**: strict mode across all services
- Pre-commit hooks enforce ruff, mypy, bandit, and detect-secrets — run `just qa` before committing

### Docker Context
The `.docker-context/` directory is **auto-generated** by `scripts/scaffold_context.py`. Never edit files inside it directly. Run `just scaffold` after adding/removing service files.

### Environment Variables
Copy `.env.example` to `.env` and set `DEEPGRAM_API_KEY`. The `.env` file is git-ignored.

## Important Docs

- [GEMINI.md](GEMINI.md) — Navigation map to all architecture docs
- [docs/20_architecture/system_design_v8.0.md](docs/20_architecture/system_design_v8.0.md) — Full technical spec
- [docs/20_architecture/architecture_definition.md](docs/20_architecture/architecture_definition.md) — C4 model
- [docs/api.md](docs/api.md) — REST/WebSocket/NATS API reference
- [ROADMAP.md](ROADMAP.md) — 4-phase plan (Ironclad → Cloud Ear → Edge Eye → Integration)
