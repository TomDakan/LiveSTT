# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Live STT** is a real-time speech-to-text appliance designed for live event environments including church services and lectures. It uses a **Split-Brain architecture**: cloud transcription (Deepgram Nova-3) runs in parallel with local biometric speaker identification (OpenVINO WeSpeaker). Designed for resilience against brief internet interruptions — audio is buffered locally so transcription can recover without gaps, but cloud STT (Deepgram) is required. Fully offline STT via a local model is a potential future addition. Runs on industrial x86 hardware (ASRock NUC N97).

## Commands

See [justfile](justfile) for all available recipes. Run `just --list` for a summary.

Always prefer `just` recipes over raw commands — they handle platform differences (Windows/WSL2/Linux) and other non-obvious environment considerations. Only fall back to raw commands when no recipe exists.

Note: `just nuke` deletes all Docker volumes and is destructive — confirm before running.

## Architecture

Full details in [docs/20_architecture/system_design_v8.0.md](docs/20_architecture/system_design_v8.0.md). **Update the summary below when the design changes.**

### Summary (v8.0 "Buffered Brain")
8 microservices communicate exclusively via NATS JetStream. Audio flows from `audio-producer` into a pre-roll ring buffer (always-on) and a live session stream on record start. `stt-provider` pulls audio and streams it to Deepgram, publishing raw transcripts. `api-gateway` currently subscribes to raw transcripts directly (temporary — `identity-manager` will fuse transcripts + speaker ID in future). Speaker identification (`identifier`, `identity-manager`) and VAD (`audio-classifier`) are stubs.

All services extend `BaseService` ([libs/messaging/src/messaging/service.py](libs/messaging/src/messaging/service.py)) and implement `run_business_logic(js, stop_event)`. Stream configs are the source of truth in [libs/messaging/src/messaging/streams.py](libs/messaging/src/messaging/streams.py).

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
See [CONTRIBUTING.md](CONTRIBUTING.md) sections 5–6 for the full branching and merge strategy. Key points:
- Changes should always be made in a branch, not directly in `main`
- Branch names: `feat/scope/description` or `fix/scope/description`
- PRs are merged via **squash & merge** — the squash commit message must be a valid Conventional Commit
- Conventional commits drive automatic semantic versioning — **never manually edit version numbers**

### Code Style
- **Ruff**: line-length=90, double quotes, target py312
- **MyPy**: strict mode across all services — always run via `just type-check` (never bare `uv run mypy .` at repo root, which scans `libs/` twice and produces false errors)
- Pre-commit hooks enforce ruff, mypy, bandit, and detect-secrets — run `just qa` before committing
- Design standards (OOP patterns, dataclasses, dependency injection, Protocol interfaces): see [docs/implementation_guides/00_workflow.md](docs/implementation_guides/00_workflow.md)

### Adding a New Service
When scaffolding a new service, update **two places** in [pyproject.toml](pyproject.toml):
1. `[tool.basedpyright] extraPaths` — add `"services/<name>/src"`
2. `[dependency-groups] dev` — add the package name (so it is installed in the root venv)

Test directory rules (violations break `just test` for the whole repo):
- **Do not create `services/<name>/tests/__init__.py`** — the service-level `__init__.py` files (which enable `just test-service <name>`) cause pytest to walk up to `services/` when both are present, producing `ModuleNotFoundError` during collection
- Use **absolute imports** in test conftest files (e.g. `from mock_transcriber import ...`), not relative imports — `tests/` is intentionally not a Python package

### Docker Context
The `.docker-context/` directory is **auto-generated** by `scripts/scaffold_context.py`. Never edit files inside it directly. Run `just scaffold` after adding/removing service files.

### Environment Variables
Copy `.env.example` to `.env` and set `DEEPGRAM_API_KEY`. The `.env` file is git-ignored.

## Important Docs

- [docs/20_architecture/system_design_v8.0.md](docs/20_architecture/system_design_v8.0.md) — Full technical spec
- [docs/20_architecture/architecture_definition.md](docs/20_architecture/architecture_definition.md) — C4 model
- [docs/api.md](docs/api.md) — REST/WebSocket/NATS API reference
- [ROADMAP.md](ROADMAP.md) — 4-phase plan (Ironclad → Cloud Ear → Edge Eye → Integration)
