# Software Bill of Materials (SBOM)

## Overview
This document catalogs all software dependencies, Docker base images, and third-party libraries used in the Live STT system.

---

## 1. Docker Base Images

| Service | Base Image | Version | Source | Security Scan |
|---------|------------|---------|--------|---------------|
| **broker** | `scratch` | N/A | Docker Hub | ✅ No vulnerabilities (empty image) |
| **audio-producer** | `python:3.13-slim` | 3.13.1 | Docker Hub Official | ✅ Scanned weekly |
| **stt-provider** | `python:3.13-slim` | 3.13.1 | Docker Hub Official | ✅ Scanned weekly |
| **api-gateway** | `python:3.13-slim` | 3.13.1 | Docker Hub Official | ✅ Scanned weekly |
| **audio-classifier** | `python:3.13-slim` | 3.13.1 | Docker Hub Official | ✅ Scanned weekly |
| **identifier** (Tier 1) | `nvcr.io/nvidia/l4t-pytorch` | r36.2.0 (Py 3.10) | NVIDIA NGC | ✅ Locked to JetPack version |
| **identifier** (Tier 2) | `pytorch/pytorch` | 2.1.0 (Py 3.10) | Docker Hub | ✅ PyTorch official |
| **health-watchdog** | `python:3.13-slim` | 3.13.1 | Docker Hub Official | ✅ Scanned weekly |

---

## 2. Python Dependencies

### Core Services (audio-producer, stt-provider, api-gateway)

Generated from `uv.lock` (pinned versions):

| Package | Version | License | Purpose | CVE Status |
|---------|---------|---------|---------|------------|
| **deepgram-sdk** | 3.3.6 | MIT | Deepgram API client | ✅ No known CVEs |
| **fastapi** | 0.110.0 | MIT | Web framework (api-gateway) | ✅ No known CVEs |
| **uvicorn** | 0.27.1 | BSD-3 | ASGI server | ✅ No known CVEs |
| **sounddevice** | 0.4.6 | MIT | Audio capture | ✅ Actively maintained (PortAudio wrapper) |
| **pyzmq** | 25.1.2 | LGPL+BSD | ZMQ bindings | ✅ No known CVEs |
| **numpy** | 1.26.4 | BSD | Audio processing | ✅ No known CVEs |
| **sqlalchemy** | 2.0.27 | MIT | ORM for config.db | ✅ No known CVEs |
| **cryptography** | 42.0.5 | Apache-2.0/BSD | AES encryption | ✅ No known CVEs |
| **pydantic** | 2.6.3 | MIT | Data validation | ✅ No known CVEs |
| **python-multipart** | 0.0.9 | Apache-2.0 | File uploads | ✅ No known CVEs |

**Full Dependency Tree**: See `uv.lock` (150+ transitive dependencies)

### ML Services (audio-classifier, identifier)

| Package | Version | License | Purpose | CVE Status |
|---------|---------|---------|---------|------------|
| **torch** | 2.1.0 | BSD-3 | PyTorch (identifier) | ✅ No known CVEs |
| **torchaudio** | 2.1.0 | BSD-2 | Audio preprocessing | ✅ No known CVEs |
| **speechbrain** | 0.5.16 | Apache-2.0 | Speaker identification | ✅ No known CVEs |
| **tensorflow-lite** | 2.15.0 | Apache-2.0 | YAMNet inference | ✅ No known CVEs |

---

## 3. System Libraries (Debian packages in Docker images)

| Package | Version | Purpose | Included In |
|---------|---------|---------|-------------|
| **libportaudio2** | 19.6.0-1.2 | PyAudio backend | audio-producer |
| **libzmq5** | 4.3.4-1 | ZMQ library | broker, all services |
| **libsqlite3-0** | 3.40.1-2 | SQLite library | api-gateway |
| **libssl3** | 3.0.11-1 | TLS support | stt-provider (Deepgram WSS) |
| **ca-certificates** | 20230311 | Root CA certs | All services |

**Security Updates**: Automatically applied via `apt-get update && apt-get upgrade` in Dockerfile

---

## 4. Pre-Trained ML Models

| Model | Version | Source | License | Size | CVE Status |
|-------|---------|--------|---------|------|------------|
| **YAMNet** | TFLite (2021) | TensorFlow Hub | Apache-2.0 | 10 MB | ✅ No known issues |
| **ECAPA-TDNN** | SpeechBrain | Hugging Face | Apache-2.0 | 500 MB | ✅ No known issues |

**Download Location**: Models pulled during Docker build from public repositories

---

## 5. JavaScript Dependencies (Web UI)

**None** - The Live STT web UI uses vanilla JavaScript (no npm dependencies)

**Static Assets**:
- `styles.css` - Custom CSS (no frameworks)
- `app.js` - WebSocket client (vanilla JS)

**Rationale**: Minimize attack surface, no npm supply chain risk

---

## 6. Build Tools (Development Only)

| Tool | Version | Purpose | Used In |
|------|---------|---------|---------|
| **uv** | latest | Python dependency manager | CI/CD, local dev |
| **ruff** | 0.2.2 | Linter & formatter | CI/CD, pre-commit |
| **mypy** | 1.8.0 | Type checker | CI/CD |
| **pytest** | 8.0.2 | Test runner | CI/CD |
| **docker** | 25.0.3 | Container runtime | All environments |
| **docker-compose** | 2.24.6 | Multi-container orchestration | Tier 2/3 |

---

## 7. Third-Party Services

| Service | Provider | Purpose | License/Terms | Data Shared |
|---------|----------|---------|---------------|-------------|
| **Deepgram API** | Deepgram Inc. | Cloud STT | Commercial (pay-per-use) | PCM audio only |
| **BalenaCloud** | Balena Inc. | Fleet management | Free tier (10 devices) | Docker images, logs |

**Data Residency**:
- **Deepgram**: Audio processed in US East (configurable)
- **BalenaCloud**: Metadata stored in AWS (EU/US)

---

## 8. License Compliance

### Permissive Licenses (No Attribution Required in Binary)
- **MIT**: 80% of dependencies
- **Apache-2.0**: 15% of dependencies
- **BSD-3**: 5% of dependencies

### Copyleft Licenses (Must Distribute Source)
- **LGPL**: pyzmq (dynamically linked, compliant)
- **GPL-3.0**: Live STT codebase (must provide source to users)

**Compliance**: All dependencies compatible with GPL-3.0

---

## 9. Vulnerability Scanning

### Automated Scans (CI/CD)
```bash
# Python dependencies
safety check --json

# Docker images
docker scan live-stt/api-gateway:latest
```

**Frequency**:
- **On Commit**: Static analysis (Bandit) - *Prevent new vulnerabilities in code*
- **Daily**: Dependency scanning (Safety, Trivy) - *Detect newly disclosed CVEs in dependencies*
- **Weekly**: Full container scan - *Deep audit of base images*

### Automated Audits (Scheduled)
- **Frequency**: Weekly (GitHub Actions / Dependabot)
- **Tools**: `pip-audit`, Snyk, Dependabot
- **SLA**: Critical CVEs patched within 24 hours (auto-PR creation)

---

## 10. Dependency Update Policy

| Severity | Target SLA | Notification |
|----------|-----------|--------------|
| **Critical** (CVSS 9.0+) | 24 hours | email |
| **High** (CVSS 7.0-8.9) | 7 days | GitHub issue |
| **Medium** (CVSS 4.0-6.9) | 30 days | Automated monthly audit |
| **Low** (CVSS 0.1-3.9) | Best effort | Automated quarterly audit |

**Version Pinning**: All production dependencies pinned in `uv.lock` (reproducible builds)

---

## 11. SBOM Export Formats

### CycloneDX (JSON)
```bash
# Pending uv support
# uv export --format cyclonedx > sbom-cyclonedx.json
```

### SPDX (RDF)
```bash
# Pending uv support
# uv export --format spdx > sbom-spdx.rdf
```

**Storage**: Committed to `/docs/60_ops/sbom/` directory with each release

---

**See Also:**
- [CI/CD](cicd.md) - Automated security scans
- [Secrets Manifest](secrets_manifest.md) - Credential inventory
- [Threat Model](../20_architecture/threat_model.md) - Supply chain risks
