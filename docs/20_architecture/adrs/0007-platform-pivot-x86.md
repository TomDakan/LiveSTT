# ADR-0007: Platform Pivot to Industrial x86

**Date**: 2025-11-26  
**Status**: ACCEPTED  
**Context**:  
The initial v6.x architecture relied on the NVIDIA Jetson Orin Nano (ARM64) to perform both transcription and biometric identification on the edge. However, during testing and review, several critical issues emerged:
1.  **Resource Contention**: Running STT and Biometrics simultaneously caused OOM (Out of Memory) kills.
2.  **Filesystem Corruption**: The Jetson lacks native Power Loss Protection (PLP), leading to corruption during power cuts.
3.  **Complexity**: Managing custom ARM builds and JetPack dependencies increased maintenance burden.

**Decision**:  
We will pivot the hardware platform to the **ASRock Industrial NUC BOX-N97** (Intel N97 x86).

**Rationale**:
1.  **Reliability**: The NUC is fanless (0dB) and supports standard x86 Linux distributions (BalenaOS).
2.  **PLP Support**: The M.2 slot supports Industrial NVMe drives with hardware Power Loss Protection.
3.  **Simplicity**: Standard x86 Docker containers eliminate cross-compilation headaches.
4.  **Cost**: The NUC ($240) is significantly cheaper than the Jetson Orin Nano ($499).

**Consequences**:
-   **Positive**: "Set and Forget" reliability, lower cost, easier development.
-   **Negative**: Loss of NVIDIA GPU requires migrating biometrics to OpenVINO (Intel iGPU).
-   **Mitigation**: OpenVINO on Intel N97 is sufficient for the "Split-Brain" architecture where heavy STT is offloaded to the cloud.
