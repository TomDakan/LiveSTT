# Multi-Tier Hardware Strategy

* **Status:** Accepted
* **Date:** 2025-11-19

---

## Context

The Live STT system requires GPU acceleration for optional features (speaker identification via SpeechBrain), but must also support:

1. **Development**: Developers on laptops without NVIDIA GPUs
2. **Testing**: CI/CD pipelines on cloud runners (CPU-only)
3. **Production**: Jetson Orin Nano (embedded ARM64 + CUDA)
4. **BYOD Deployment**: Users with desktop GPUs (x64 + CUDA/ROCm)

The system must be **portable across hardware tiers** without maintaining separate codebases per platform.

---

## Decision

We will implement a **Three-Tier Hardware Strategy** with conditional feature enablement:

### Hardware Tiers
| Tier | Target Hardware | GPU | Arch | Services Enabled |
|------|----------------|-----|------|------------------|
| **Tier 1** | Jetson Orin Nano | NVIDIA (CUDA) | ARM64 | All (including `identifier`) |
| **Tier 2** | Desktop GPU | NVIDIA/AMD | x86_64 | All (including `identifier`) |
| **Tier 3** | CPU-only | None | x86_64 | Core stack (no `identifier`) |

### Implementation Strategy

**1. Unified Dockerfile with Build Args**
```dockerfile
# services/identifier/Dockerfile
ARG BASE_IMAGE=python:3.13-slim  # Default: Tier 3
FROM ${BASE_IMAGE}

# GPU dependencies only installed if base image has CUDA
RUN if [ -f /usr/local/cuda/version.txt ]; then \
      pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121; \
    else \
      pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu; \
    fi
```

**2. Docker Compose Profiles**
```yaml
services:
  identifier:
    profiles: ["gpu"]  # Only started with `docker compose --profile gpu up`
    build:
      context: ./services/identifier
      args:
        BASE_IMAGE: ${IDENTIFIER_BASE_IMAGE:-python:3.13-slim}
```

**3. Hardware-Specific Overrides**
```bash
# Tier 1 (Jetson)
export IDENTIFIER_BASE_IMAGE=nvcr.io/nvidia/l4t-pytorch:r36.2.0-pth2.1-py3

# Tier 2 (Desktop GPU)
export IDENTIFIER_BASE_IMAGE=pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

# Tier 3 (CPU)
# Use default (no override needed)
```

---

## Consequences

### Positive
- **Single codebase**: No platform-specific branches
- **Zero-config for Tier 3**: Developers can run `docker compose up` without modifications
- **Graceful degradation**: Core transcription works on all tiers, GPU features optional
- **Future-proof**: Can add Tier 4 (Cloud TPU), Tier 5 (WebGPU), etc. with same pattern

### Negative
- **Build complexity**: Developers must understand build args and profiles
- **Testing matrix**: Must test on all 3 tiers (CI runs Tier 3, manual testing on Tier 1/2)
- **Documentation burden**: Must clearly document which features require GPU

### Risks and Mitigations
- **Risk**: User tries to run `identifier` on Tier 3, gets cryptic error
  - **Mitigation**: `identifier` service checks for GPU at startup, exits gracefully with clear message
- **Risk**: Image size bloat (CUDA libraries in Tier 1/2 images)
  - **Mitigation**: Multi-stage builds, separate dev/prod images

---

## Alternatives Considered

### Alternative 1: Separate Repositories per Tier
**Why rejected**:
- Code duplication (bug fixes must be ported across repos)
- Fragmented documentation
- Difficult to ensure feature parity

### Alternative 2: Runtime GPU Detection
**Why rejected**:
- Still requires bundling GPU libraries in all images (bloat)
- Startup time increased by probing hardware
- Harder to test (cannot force CPU mode on GPU machine)

### Alternative 3: Cloud-Only GPU (Offload to AWS Lambda)
**Why rejected**:
- Violates edge-first architecture
- Adds latency (network round-trip for every identification)
- Additional ongoing costs (AWS Lambda)

---

## References

- [System Design](../../system_design.md) - Section 2.2 (Hardware Tiers)
- [Deployment Runbooks](../../60_ops/runbooks.md) - Tier-specific deploy procedures
- [Hardware BOM](../../40_hardware/hbom.md) - Recommended hardware per tier
