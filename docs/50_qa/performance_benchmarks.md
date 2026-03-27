# Performance Benchmarks

## 1. Overview
This document defines the performance targets (SLAs) and benchmarking methodology for the Live STT system.

---

## 2. Key Performance Indicators (KPIs)

### 2.1 Latency
**Definition**: Time from sound wave hitting microphone to text appearing on Web UI.

| Metric | Target | Max Acceptable | Measurement Method |
|--------|--------|----------------|-------------------|
| **Glass-to-Glass Latency** | < 500ms | 1000ms | High-speed camera (clap test) |
| **Deepgram Processing** | < 300ms | 500ms | API response timestamp delta |
| **Local Processing** | < 50ms | 100ms | Internal log timestamps |
| **Network RTT** | < 50ms | 150ms | `ping api.deepgram.com` |

### 2.2 Throughput & Stability
| Metric | Target | Notes |
|--------|--------|-------|
| **Continuous Runtime** | 4 hours | Typical Sunday service length |
| **Memory Usage (Tier 1)** | < 6GB | Total system RAM (16GB available) |
| **CPU Usage (Tier 1)** | < 50% avg | Leave headroom for OS/bursts |
| **Disk I/O** | < 10MB/s | NVMe bandwidth is plenty |

### 2.3 Accuracy (WER)
**Word Error Rate** targets for "Church Audio" domain:

| Scenario | Target WER | Notes |
|----------|------------|-------|
| **Clear Speech (Sermon)** | < 5% | Single speaker, good mic |
| **Liturgy (Reading)** | < 3% | Predictable text |
| **Discussion (Meeting)** | < 10% | Overlapping speech, casual |
| **Music/Singing** | N/A | Should be ignored by classifier |

---

## 3. Benchmark Scenarios

### Scenario A: Standard Load
- **Input**: 16kHz Mono WAV (Sermon)
- **Services**: All enabled (including identifier)
- **Clients**: 10 WebSocket listeners
- **Hardware**: Tier 1 (Industrial x86 NUC)

### Scenario B: Stress Test
- **Input**: High-density speech (auctioneer style)
- **Services**: All enabled
- **Clients**: 50 WebSocket listeners
- **Network**: Simulated 5% packet loss, 200ms jitter

### Scenario C: Recovery Test
- **Action**: Disconnect WAN for 5 minutes
- **Metric**: Time to catch up after reconnection
- **Target**: Catch-up speed > 2x real-time (e.g., 5 min buffer processed in < 2.5 min)

---

## 4. Baseline Results (Estimated)

| Component | Latency Contribution | Notes |
|-----------|----------------------|-------|
| **Audio Capture** | 50ms | 1600 sample buffer @ 16kHz |
| **ZMQ Broker** | < 1ms | Zero-copy transport |
| **Network RTT** | 40ms | Fiber connection to US East |
| **Deepgram API** | 250ms | Streaming inference |
| **Web UI Render** | 20ms | DOM update |
| **Total** | **~361ms** | **Passes Target (<500ms)** |

---

## 5. Load Testing Tools

### `locust` (WebSocket Load)
Used to simulate multiple client connections to the API Gateway.

```python
# locustfile.py
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(1, 5)

    @task
    def view_transcript(self):
        self.client.get("/")
        # Note: Real test needs WebSocket client simulation
```

### `stress-ng` (System Stress)
Used to verify stability under CPU/Memory pressure.
```bash
stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 1G --timeout 60s
```

---

## 6. Optimization Tuning

If targets are missed, tune these parameters:

1. **Audio Buffer Size**:
   - Current: 1600 samples (100ms)
   - Tuning: Reduce to 800 samples (50ms) → Reduces capture latency by 50ms
   - Risk: Increased CPU overhead, potential dropouts

2. **Deepgram Model**:
   - Current: `nova-3` (balanced)

---

**See Also:**
- [Master Test Plan](master_test_plan.md) - Testing strategy
- [Environmental Constraints](../40_hardware/environmental_constraints.md) - Hardware limits
