# 10. Upgrade to Python 3.12

Date: 2025-11-28

## Status

Accepted

## Context

The project is pivoting from NVIDIA Jetson hardware (ARM64) to an Industrial x86 platform (Intel N97). This hardware change removes the constraints of NVIDIA JetPack, which would have locked the system to Python 3.10 until Nvidia released a new version of JetPack.

We have an opportunity to modernize the technology stack.
- **Current State**: Mixed Python versions (3.10 in root, 3.11 in `audio-producer`).
- **Drivers**:
    - Need for modern Python features and performance improvements.
    - `audio-producer` already requires Python 3.11+.
    - `deepgram-sdk` (a critical dependency) supports up to Python 3.12.
    - Python 3.13 is still experimental for some key libraries (OpenVINO).

## Decision

We will standardize the entire monorepo on **Python 3.12**.

This version provides the best balance of:
1.  **Modernity**: Access to latest language features and performance improvements.
2.  **Stability**: Fully supported by all critical dependencies (`deepgram-sdk`, `nats-py`, `openvino`, `lancedb`).
3.  **Longevity**: Ensures a long support window before the next major upgrade is needed.

## Consequences

1.  **Root Configuration**: The root `pyproject.toml` will be updated to require Python `>=3.12`.
2.  **Service Configuration**: All service-level `pyproject.toml` files will be updated to target Python 3.12.
3.  **Docker Images**: All Dockerfiles will be updated to use `python:3.12-slim` (or equivalent) base images.
4.  **CI/CD**: CI pipelines must be updated to use Python 3.12 runners.
5.  **Dev Environment**: Developers will need to upgrade their local Python environment to 3.12.
