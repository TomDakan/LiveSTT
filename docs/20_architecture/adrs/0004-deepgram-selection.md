# Select Deepgram as STT Provider

* **Status:** Accepted
* **Date:** 2025-11-19

---

## Context

The Live STT system requires a cloud-based Speech-to-Text (STT) service with the following requirements:

1. **Real-time streaming**: WebSocket-based, not batch transcription
2. **High accuracy**: Church liturgy, biblical terminology, proper nouns (staff names)
3. **Endpointing**: Automatic sentence segmentation (reduces UI flicker)
4. **Custom vocabulary**: Support for domain-specific phrases (e.g., "Eucharist", "homily")
5. **Speaker diarization**: Distinguish multiple speakers (optional but preferred)
6. **Resilience**: Graceful handling of connection drops, support for audio catch-up

**Non-Requirements**:
- On-device STT (GPU constraints on Jetson, model size)
- Multi-language support (English-only for V1)

---

## Decision

We will use **Deepgram** as the primary STT provider.

### Integration Details
- **API**: Deepgram Live Streaming API (WebSocket)
- **Model**: `nova-2` (latest general model)
- **Features Used**:
  - `punctuate=true`: Automatic punctuation
  - `diarize=true`: Speaker labels (Speaker 0, Speaker 1, ...)
  - `smart_format=true`: Format numbers, dates
  - `keywords`: Custom PhraseSet ([initial_phrases.json](../../config/initial_phrases.json))
  - `endpointing=300`: 300ms silence triggers utterance boundary

### Example Connection
```python
from deepgram import DeepgramClient, LiveOptions

client = DeepgramClient(api_key=os.getenv("DEEPGRAM_API_KEY"))
options = LiveOptions(
    model="nova-2",
    punctuate=True,
    diarize=True,
    smart_format=True,
    keywords=["Eucharist:5", "homily:5"],  # Boost weight
    endpointing=300
)
connection = client.listen.websocket.v("1")
```

---

## Consequences

### Positive
- **Superior accuracy**: Deepgram Nova-2 achieves ~90% WER on general speech (subjectively better than competitors on liturgical content)
- **Low latency**: Typically \<300ms from audio chunk → transcript event
- **Excellent docs**: Python SDK well-maintained, WebSocket reconnection handled by library
- **Custom vocabulary**: PhraseSet API allows boosting rare terms without retraining
- **Generous pricing**: \$0.0043/min (vs. Google \$0.006/min, AWS \$0.024/min)

### Negative
- **Cloud dependency**: Requires persistent internet (mitigated by on-disk buffering in `stt-provider`)
- **Vendor lock-in**: Switching to different STT provider requires rewriting `stt-provider` client code
- **No on-prem option**: Cannot run Deepgram models locally (acceptable for V1)

### Risks and Mitigations
- **Risk**: Deepgram API outage
  - **Mitigation**: Buffer audio to NVMe during outages ([M5](../../roadmap_draft.md#milestone-5)), catch up on reconnect
- **Risk**: API pricing changes
  - **Mitigation**: Budget monitoring, fallback to Google Cloud STT if costs spike
- **Risk**: Diarization errors (Speaker 0 vs Speaker 1 swapped)
  - **Mitigation**: Local speaker identification with `identifier` service overrides Deepgram labels ([M12](../../roadmap_draft.md#milestone-12))

---

## Alternatives Considered

### Alternative 1: Google Cloud Speech-to-Text
**Pros**:
- Excellent accuracy (comparable to Deepgram)
- Native GCP integration (if using GCP for other services)

**Why rejected**:
- **40% higher cost** (\$0.006/min vs \$0.0043/min)
- Worse WebSocket reconnection handling (manual exponential backoff required)
- PhraseSet boosting less effective (anecdotal)
- reports of worse diarization accuracy

### Alternative 2: AWS Transcribe
**Pros**:
- Native AWS integration
- Support for custom vocabulary

**Why rejected**:
- **5x higher cost** (\$0.024/min)
- Batch-only transcription (streaming via HTTP Live requires polling)
- No native speaker diarization (requires Amazon Transcribe Medical)

### Alternative 3: Azure Speech Services
**Pros**:
- Good accuracy
- Native Azure integration

**Why rejected**:
- **3x higher cost** (\$0.015/min)
- Requires Azure account (all other infrastructure is Docker-based)
- SDK less mature than Deepgram (more boilerplate)

### Alternative 4: Whisper (OpenAI) - On-Device
**Pros**:
- Free (open-source model)
- No cloud dependency
- Excellent accuracy

**Why rejected**:
- **Inference latency**: \~2-5 seconds per 30s chunk on Jetson (unacceptable for real-time)
- **VRAM requirements**: \~3GB for `medium` model (Jetson only has 8GB total)
- **No streaming**: Must buffer audio in chunks, sends "bursts" of transcripts (poor UX)

---

## References

- [Deepgram Documentation](https://developers.deepgram.com/)
- [stt-provider Implementation](../../services/stt-provider/) - Integration code
- [PhraseSet Seed Data](../../config/initial_phrases.json) - Custom vocabulary
- [Roadmap M3](../../roadmap_draft.md#milestone-3) - stt-provider development milestone
