# Environmental Constraints (v8.0)

## Overview
This document defines the operating environment requirements and constraints for the Live STT system (v7.3 Industrial Split-Brain).

---

## 1. Physical Environment

### Temperature
| Tier | Operating Range | Storage Range | Notes |
|------|----------------|---------------|-------|
| **Tier 1 (NUC N97)** | 0°C to 40°C | -20°C to 60°C | **Passive Cooling**: Requires airflow (do not enclose in airtight box) |
| **Tier 2 (Desktop)** | 10°C to 35°C | -20°C to 60°C | Standard desktop PC range |

**Church Sanctuary Typical**: 18-24°C (65-75°F)

### Humidity
- **Operating**: 20% to 80% RH (non-condensing)
- **Storage**: 5% to 95% RH (non-condensing)

### Noise
- **Requirement**: **0dB (Silent)**
- **Implementation**: Fanless Chassis (ASRock NUC BOX-N97)
- **Constraint**: No moving parts allowed (no HDD, no fans).

---

## 2. Power Requirements

### Tier 1 (ASRock NUC N97)
| Parameter | Specification | Notes |
|-----------|---------------|-------|
| **Input Voltage** | 12V-19V DC | 12V/3A Adapter included |
| **Peak Power** | 25W | During boot / heavy inference |
| **Idle Power** | 6W | Silent periods |
| **Typical Power** | 10W | Continuous transcription + ID |

**Power Conditioning**:
- **PLP Protection**: Transcend MTE712A NVMe handles sudden power loss.
- **UPS Optional**: Recommended for graceful shutdown, but not strictly required for data integrity due to PLP + Journaling.

---

## 3. Network Requirements

### Bandwidth
| Direction | Min | Recommended | Purpose |
|-----------|-----|-------------|---------|
| **Upload** | 300 kbps | 500 kbps | Audio stream to Deepgram (Linear16 PCM) |
| **Download** | 10 kbps | 50 kbps | Transcript JSON from Deepgram |
| **WebSocket Clients** | 5 kbps/client | 10 kbps/client | Broadcast transcripts to 30 clients |

### Latency
- **Target**: < 500ms (Text), < 100ms (Identity)
- **Deepgram Nova-3**: ~300ms processing time

### Firewall Requirements
| Protocol | Direction | Port | Destination | Purpose |
|----------|-----------|------|-------------|---------|
| **WSS** | Outbound | 443 | api.deepgram.com | STT streaming |
| **HTTPS** | Outbound | 443 | balena-cloud.com | Fleet management |

---

## 4. Acoustic Environment

### Microphone Placement
- **Distance**: 1-3 meters (3-10 feet)
- **Mounting**: Shock mount recommended to avoid podium vibrations.

### Background Noise
- **Limit**: < 50dB SPL for optimal accuracy.
- **Music Handling**: `audio-classifier` (roadmap) or manual pause recommended during worship music.

### Audio Chain
- **Source**: Focusrite Scarlett Solo (Line Level)
- **Sample Rate**: 48kHz (Hardware Native) → Resampled to 16kHz (Software)
- **Bit Depth**: 24-bit (Hardware) → 16-bit (Software)

---

## 5. Maintenance

### Tier 1 (NUC)
| Task | Frequency | Procedure |
|------|-----------|-----------|
| **Dust Cleaning** | Annually | Compressed air (heatsink fins) |
| **NVMe Health** | Monthly | Automated SMART check |
| **Reboot** | Weekly | Automated via Balena (Sunday 3AM) |

---

**See Also:**
- [HBOM](hbom.md) - Component specifications
- [Assembly Guide](assembly_guide.md) - Setup instructions
