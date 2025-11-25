# Frequently Asked Questions (FAQ)

## General

### Q: Does this system require the internet?
**A:** Yes and No. 
- **Yes**: It needs internet to send audio to Deepgram for transcription.
- **No**: It is "Offline-First" in design. If the internet cuts out, it will buffer audio locally and upload it when the connection returns. It will not crash.

### Q: Why not use Whisper running locally?
**A:** We evaluated Whisper (see [ADR-0004](../20_architecture/adrs/0004-deepgram-selection.md)). While accurate, the latency on the Jetson Orin Nano for real-time streaming was too high (>1s) for a live captioning experience. Deepgram offers <300ms latency. We may revisit this as hardware improves.

### Q: Can I use a Raspberry Pi instead of a Jetson?
**A:** You can run the core transcription stack (Tier 3) on a Raspberry Pi 4/5. However, the **Speaker Identification** feature requires a GPU for acceptable performance. On a Pi, speaker ID would be too slow or disabled.

---

## Operations

### Q: How do I add a new speaker?
**A:** Currently, this is done via the API or CLI. A proper Web UI for enrollment is planned for v1.5. See the [Biometric Policy](../30_data/biometric_policy.md) for the enrollment script.

### Q: What happens if the power goes out?
**A:** The device should be on a UPS. If power is lost abruptly, the filesystem is journaled (ext4) and should recover, but the current audio buffer in RAM will be lost.

### Q: How much bandwidth does it use?
**A:** Very little. About 50-100 kbps upload for the compressed audio stream. A standard DSL or 4G connection is sufficient.

---

## Troubleshooting

### Q: The transcript is stuck / not showing up.
**A:** 
1. Check if the "On Air" light is active on the device.
2. Check your internet connection.
3. Refresh the web page.
4. See [Runbooks](../60_ops/runbooks.md) for detailed logs analysis.

### Q: It keeps identifying the wrong person.
**A:** 
- The speaker might be too far from the mic.
- The voiceprint might be poor quality. Try re-enrolling the user.
- Adjust the confidence threshold in the config.
