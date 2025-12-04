# ADR-0008: Industrial Split-Brain Architecture

**Date**: 2025-11-26
**Status**: ACCEPTED
**Context**:
We need high-accuracy transcription (comparable to human captioning) AND low-latency speaker identification.
-   **Pure Edge (v6.x)**: Jetson STT models (Whisper-small) are not accurate enough for church sermons.
-   **Pure Cloud**: Cloud diarization is good but cannot identify specific local speakers (e.g., "Pastor John") by name without training custom models, which is expensive and complex.

**Decision**:
Adopt a **"Split-Brain" Architecture** with a **Hybrid Tagging Strategy**.

**Details**:
1.  **Cloud Ear**: Audio is streamed to **Deepgram Nova-3** for high-accuracy text and segmentation (Speaker A, Speaker B).
2.  **Edge Eye**: Audio is locally processed by **OpenVINO (WeSpeaker)** to identify specific users (Speaker A = "Alice").
3.  **Hybrid Tagging**: A local "Identity Manager" service correlates the two streams. It uses Deepgram's timestamps for *when* someone spoke and the local biometric result to *tag* the segment with the correct name.

**Consequences**:
-   **Positive**: Best of both worlds—Cloud accuracy + Edge privacy/identity.
-   **Negative**: Increased architectural complexity (synchronizing two streams).
-   **Mitigation**: Use NATS messaging and a "Time Zipper" service to reliably merge the streams based on system uptime timestamps.
