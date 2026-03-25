# Audio Chunk Size Standardisation

**Date**: 2026-03-25
**Status**: ACCEPTED

**Context**:
The audio-producer was publishing PCM chunks of 1600 samples (100ms at 16kHz). The data dictionary incorrectly documented this as 800 samples / 50ms — a pre-existing inconsistency. When implementing the audio-classifier using Silero VAD, the model requires chunk sizes of exactly 512, 1024, or 1536 samples at 16kHz. Accepting arbitrary chunk sizes would require buffering and re-chunking logic in the classifier, adding complexity without benefit.

**Decision**:
Standardise the published audio chunk size to **1536 samples (96ms at 16kHz, 3072 bytes)**.

- 1536 is a native Silero VAD input size — the audio-classifier can run inference directly on each NATS message with no pre-processing.
- It is the closest valid Silero size to the previous 1600-sample default, minimising behavioural change to the rest of the pipeline.
- Deepgram's WebSocket streaming API is chunk-size agnostic; this change has no impact on STT quality or latency.
- All audio sources (FileSource, LinuxSource, WindowsSource) updated to default to 1536.
- Data dictionary corrected to match.

**Consequences**:
- **Positive**: Eliminates re-chunking overhead in the audio-classifier. Resolves the 1600 vs 800 sample inconsistency between code and documentation.
- **Negative**: Chunk duration changes from 100ms to 96ms — immaterial for all current consumers.
- **Note**: Future consumers requiring a different granularity should buffer internally rather than changing the published chunk size.
