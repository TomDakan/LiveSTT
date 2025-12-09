# GEMINI.md - Context & Navigation

> [!IMPORTANT]
> **CRITICAL INSTRUCTION FOR LLMS:**
> This file is the MAP. The TRUTH is in the linked files below.
> You MUST read the specific files linked here to understand the current project state.

## 1. Architecture & Specs
*   **Active System Design**: [docs/20_architecture/system_design_v8.0.md](docs/20_architecture/system_design_v8.0.md) (READ THIS FIRST)
    *   *Contains*: Hardware Topology, Data Path ("Buffered Split-Brain"), Component Design, Microservices.
*   **Hardware Constraints**: See "Hardware Topology" in the design doc above.
*   **IPC Pattern**: See "Component Design" in the design doc above (currently NATS JetStream).

## 2. Development Standards
*   **Workflow & Commands**: [CONTRIBUTING.md](CONTRIBUTING.md)
*   **Branching & Merging**: See [CONTRIBUTING.md](CONTRIBUTING.md) section 6 (Conventional Commits, Squash & Merge)
*   **Dependency Management**: See [CONTRIBUTING.md](CONTRIBUTING.md) section 7 (Lock-Step Versioning, workspace dependencies)
*   **AI Collaboration**: [docs/implementation_guides/00_workflow.md](docs/implementation_guides/00_workflow.md)
*   **Coding Style**: [CONTRIBUTING.md](CONTRIBUTING.md) section 8.
*   **Platform Support**: Some services (like `audio-producer`) have platform-specific dependencies (e.g., ALSA on Linux). These are handled via conditional dependencies in `pyproject.toml`.

## 3. Current Status
*   **Active Roadmap**: [ROADMAP.md](ROADMAP.md)
