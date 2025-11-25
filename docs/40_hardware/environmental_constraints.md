# Environmental Constraints

## Overview
This document defines the operating environment requirements and constraints for the Live STT system across all deployment tiers.

> [!NOTE]
> Specific equipment models mentioned throughout this document (e.g., APC UPS, specific GPU models) are **illustrative examples only**, not official recommendations or endorsements. Use equivalent components that meet the specified requirements.

---

## 1. Physical Environment

### Temperature
| Tier | Operating Range | Storage Range | Notes |
|------|----------------|---------------|-------|
| **Tier 1 (Jetson)** | 0°C to 50°C | -20°C to 60°C | Passive cooling: 0-35°C, Active cooling: 0-50°C |
| **Tier 2 (Desktop)** | 10°C to 35°C | -20°C to 60°C | Standard desktop PC range |
| **Tier 3 (CPU-Only)** | N/A | N/A | Standard office/home environment |

**Church Sanctuary Typical**: 18-24°C (65-75°F)

### Humidity
- **Operating**: 20% to 80% RH (non-condensing)
- **Storage**: 5% to 95% RH (non-condensing)

**Risk Mitigation**: Avoid placement near HVAC vents (rapid humidity changes)

### Altitude
- **Operating**: Up to 3000m (9843 ft)
- **Storage**: Up to 4500m (14764 ft)

### Vibration & Shock
- **Operating**: 0.5G (typical office environment)
- **Transport**: 2G shock (in protective case)

**Church Deployment**: Minimal vibration (no industrial machinery nearby)

---

## 2. Power Requirements

### Tier 1 (Jetson Orin Nano)
| Parameter | Specification | Notes |
|-----------|---------------|-------|
| **Input Voltage** | 5V DC (USB-C PD) | 5V/4A recommended |
| **Peak Power** | 25W | During GPU-intensive identifier inference |
| **Idle Power** | 7W | During silent periods (no audio processing) |
| **Typical Power** | 12W | Continuous transcription |

**Power Conditioning**:
- **UPS Recommended**: Any UPS with ≥150VA capacity (e.g., APC Back-UPS 350VA ~$40)
  - **Primary Purpose**: Graceful shutdown, survive brief power blips (\<5 min)
  - **Useful Runtime**: 10-15 minutes (PA system will also be down during outage, no audio to transcribe)
  - **Note**: Most useful for preventing filesystem corruption from sudden power loss
- **Surge Protection**: Built into USB-C PD adapter

### Tier 2 (Desktop)
- **GPU Power**: ~170W (e.g., RTX 3060 or equivalent)
- **Total System**: ~250W typical
- **UPS**: Recommend ≥600VA capacity (e.g., APC Back-UPS 600VA) for 10-15 min runtime to prevent filesystem corruption during power loss

### Tier 3 (CPU-Only / CI)
- **Power**: Standard laptop/desktop power (65W-100W typical)
- **Usage**: CI runners, dev laptops (no GPU required)

---

## 3. Network Requirements

### Bandwidth
| Direction | Min | Recommended | Purpose |
|-----------|-----|-------------|---------|
| **Upload** | 50 kbps | 100 kbps | Audio stream to Deepgram (16kHz PCM → compressed) |
| **Download** | 10 kbps | 50 kbps | Transcript JSON from Deepgram |
| **WebSocket Clients** | 5 kbps/client | 10 kbps/client | Broadcast transcripts to 30 clients |

**Total Bandwidth (Tier 1)**: ~450 kbps (0.45 Mbps) for 30 clients

### Latency
- **Target**: \<100ms RTT to Deepgram API (US East)
- **Maximum**: 500ms RTT (acceptable, adds delay)

**Typical Church Internet**: 10 Mbps down / 2 Mbps up → Sufficient

### Reliability
- **Service Availability**: 99% during scheduled operating hours (e.g., Sunday services)
- **Outage Tolerance**: 10 minutes (maximum buffer capacity before overwriting)

### Firewall Requirements
| Protocol | Direction | Port | Destination | Purpose |
|----------|-----------|------|-------------|---------|
| **WSS** | Outbound | 443 | api.deepgram.com | STT streaming |
| **HTTPS** | Inbound | 8000 | * | Web UI (if using public device URL) |
| **HTTPS** | Outbound | 443 | balena-cloud.com | Fleet management (Tier 1) |

**No Inbound Required**: Balena Public URL uses reverse tunnel (no port forwarding)

---

## 4. Acoustic Environment

### Microphone Placement
- **Distance from Speaker**: 1-3 meters (3-10 feet)
- **Mounting**: Avoid contact with vibrating surfaces (lectern, podium)
- **Obstructions**: Clear line-of-sight to speaker's mouth

### Background Noise
| Source | SPL (dB) | Mitigation |
|--------|----------|------------|
| **HVAC** | 40-50 dB | Use directional mic, noise gate |
| **Ambient Conversation** | 50-60 dB | Pause transcription during non-service times |
| **Music** | 70-90 dB | `audio-classifier` pauses STT during music |

**Signal-to-Noise Ratio**: Minimum 20 dB SNR for acceptable accuracy

### Sample Rate & Bit Depth
- **PA System Output**: Analog audio (line-level, no digital sample rate)
- **USB Interface ADC**: Typically 44.1kHz or 48kHz at 16/24-bit (hardware-dependent)
- **Recommended Configuration**: 16kHz, 16-bit if interface supports it (avoids resampling overhead)
- **audio-producer Output**: Resamples to 16kHz, 16-bit PCM for Deepgram (if needed)

---

## 5. Physical Security

### Tier 1 (Jetson in Church)
| Threat | Mitigation | Cost |
|--------|------------|------|
| **Theft** | Lock in AV rack, cable lock | $20 |
| **Tampering** | Secure Boot, TPM sealing | Built-in |
| **Accidental Damage** | Protective case | $25 |

**Placement Recommendation**: AV control room (restricted access), not public sanctuary

### Tier 2/3
- **Desktop/Laptop**: Standard physical security (locked office, screen lock)
- **CI Runners**: GitHub Actions (managed security)

---

## 6. Electromagnetic Compatibility (EMC)

### Interference Sources
| Source | Frequency | Distance | Risk |
|--------|-----------|----------|------|
| **Cell Phones** | 700-2600 MHz | \<0.5m | Low (USB audio is shielded) |
| **WiFi Router** | 2.4/5 GHz | \<1m | Low |
| **Fluorescent Lights** | 50/60 Hz harmonics | \<2m | Medium (can cause 60 Hz hum) |

**Mitigation**: Use shielded USB cables, ground PA system properly

### FCC Compliance
- **Jetson Orin Nano**: FCC Class B (residential use)
- **USB Audio Interface**: FCC Part 15 (unintentional radiator)

---

## 7. Maintenance & Serviceability

### Tier 1 (Jetson)
| Task | Frequency | Downtime | Procedure |
|------|-----------|----------|-----------|
| **Dust Cleaning** | Quarterly | 10 min | Compressed air, power off |
| **NVMe Health Check** | Monthly | 0 min | `smartctl -a /dev/nvme0n1` (manual or via systemd timer) |
| **Software Updates** | Weekly | 2 min | Balena push (zero-downtime) |
| **Full Reflash** | As Needed | 30 min | Major OS version upgrade or corruption recovery |

**NVMe Monitoring**: Can be automated with a systemd timer that logs SMART data:
```bash
# Example: /etc/systemd/system/nvme-health.timer
[Timer]
OnCalendar=monthly
Persistent=true
```

### Accessibility
- **Placement**: Accessible within 1 minute (not behind locked racks requiring keys)
- **Cables**: Label all connections (power, USB audio, network)

---

## 8. Compliance & Certifications

| Standard | Applicability | Verification |
|----------|---------------|--------------|
| **UL/CE** | Jetson, PSU | Manufacturer certification |
| **RoHS** | All components | Compliant (lead-free) |
| **ENERGY STAR** | N/A | Not applicable (custom device) |

---

## 9. Disaster Recovery

### Environmental Hazards
| Hazard | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| **Fire** | Low | Total loss | Offsite config backup (Git repository) |
| **Water Damage** | Low | Total loss | Keep away from plumbing, use waterproof case |
| **Power Surge** | Medium | Component failure | UPS with surge protection |
| **Extended Power Outage** | Medium | Graceful shutdown | UPS provides 10-15 min runtime |

### Recovery Time Objective (RTO)
- **Tier 1 Replacement**: 1 week (order new Jetson, reflash from backup)
- **Tier 2/3**: 1 day (redeploy to different hardware)

---

**See Also:**
- [HBOM](hbom.md) - Component specifications
- [Threat Model](../20_architecture/threat_model.md) - Security considerations
- [Runbooks](../60_ops/runbooks.md) - Operational procedures
