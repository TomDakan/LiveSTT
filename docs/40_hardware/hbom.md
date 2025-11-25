# Hardware Bill of Materials (HBOM)

## Overview
This document specifies the hardware components required for each deployment tier of the Live STT system.

> [!NOTE]
> All component models listed are **illustrative examples** to demonstrate viable options. They are not prescriptive recommendations or endorsements. Use equivalent components that meet the specified requirements (power, connectivity, performance).

---

## Tier 1: Production (Jetson Orin Nano)

### Core Components
| Component | Model | Quantity | Price (USD) | Purpose |
|-----------|-------|----------|-------------|---------|
| **SBC** | e.g., NVIDIA Jetson Orin Nano 8GB | 1 | $499 | Main compute (GPU for identifier service) |
| **Storage** | e.g., Samsung 980 PRO NVMe 250GB | 1 | $45 | OS + data buffering |
| **Audio Interface** | e.g., Behringer UCA202 USB | 1 | $30 | Stereo line-in from PA system |
| **Power Supply** | 5V/4A USB-C PD | 1 | $15 | Jetson power |
| **Case** | e.g., Jetson Orin Nano Developer Kit Case | 1 | $25 | Physical protection |

### Optional Components
| Component | Model | Quantity | Price (USD) | Purpose |
|-----------|-------|----------|-------------|---------|
| **Cooling** | e.g., Noctua NF-A4x10 5V Fan | 1 | $15 | Active cooling for extended use |
| **TPM Module** | e.g., Infineon SLB9670 TPM2.0 | 1 | $20 | Key sealing (if not onboard) |

**Total Cost (Tier 1)**: ~$614 - $649

---

## Tier 2: Desktop Development (x86_64 + GPU)

### Core Components
| Component | Model | Quantity | Price (USD) | Purpose |
|-----------|-------|----------|-------------|---------|
| **GPU** | e.g., NVIDIA RTX 3060 (12GB) or equivalent | 1 | $300+ | identifier service (optional) |
| **Audio Interface** | Same as Tier 1 | 1 | $30 | USB audio input |

**Notes**:
- Uses developer's existing desktop/laptop
- GPU only required if testing `identifier` service
- Can run full stack on CPU for core transcription testing

**Total Cost (Tier 2)**: ~$30 - $330 (depending on GPU)

---

## Tier 3: CI/CD & CPU-Only Development

### Core Components
| Component | Model | Quantity | Price (USD) | Purpose |
|-----------|-------|----------|-------------|---------|
| **Audio Interface** | Mock audio files (no hardware) | 0 | $0 | Testing with pre-recorded sermons |

**Notes**:
- Runs on GitHub Actions runners or developer laptops
- No `identifier` service (CPU-only)
- Suitable for integration tests, linting, type checking

**Total Cost (Tier 3)**: $0

---

## Peripheral Hardware (All Tiers)

### Audio Input Options
| Option | Model | Use Case | Est. Cost |
|--------|-------|----------|-----------|
| **USB Microphone** | e.g., Blue Yeti | Small room, direct mic | ~$100 |
| **PA System Feed** | e.g., Behringer UCA202 | Church sanctuary with existing PA | $30 |
| **XLR Interface** | e.g., Focusrite Scarlett Solo | Professional audio setup | $120 |

### Network Connectivity
| Option | Model | Use Case | Est. Cost |
|--------|-------|----------|-----------|
| **Ethernet** | CAT6 cable | Wired connection (preferred) | $10 |
| **WiFi Adapter** | e.g., Intel AX200 | Wireless backup | $20 |
| **Travel Router** | e.g., GL.iNet GL-MT300N-V2 | Portable local network | $20 |

---

## Part Selection Rationale

### Why Jetson Orin Nano?
- **GPU**: NVIDIA Ampere (1024 CUDA cores) for SpeechBrain inference
- **VRAM**: 8GB shared memory (sufficient for ECAPA-TDNN model)
- **Power**: 5-15W typical (can run on USB-C PD)
- **Linux Support**: Ubuntu 20.04 (L4T), Docker native
- **TPM**: Onboard security module for key sealing
- **Longevity**: NVIDIA Jetson platform has 10-year support lifecycle

### Why Samsung 980 PRO?
- **Performance**: 6900 MB/s read (handles 4-hour audio buffering)
- **Endurance**: 150 TBW (survives years of log writes)
- **Form Factor**: M.2 2280 (fits Jetson carrier board)

### Why Behringer UCA202?
- **Compatibility**: ALSA auto-detection (no driver needed)
- **Latency**: \<10ms round-trip (negligible vs. network latency)
- **Cost**: $30 (vs. $100+ for "audiophile" interfaces with no benefit for STT)

---

## Supply Chain & Availability

| Component | Lead Time | Availability | Alternative |
|-----------|-----------|--------------|-------------|
| Jetson Orin Nano | 2-4 weeks | Often backordered | e.g., Jetson Xavier NX (older, compatible) |
| Samsung 980 PRO | In stock | Retail (Amazon, Newegg) | e.g., WD Black SN850 |
| Behringer UCA202 | In stock | Music retailers | Any USB audio interface |

**Recommendation**: Order Jetson first (longest lead time), use Tier 3 setup while waiting.

---

## Environmental Impact

| Component | Power (Watts) | Annual kWh | Annual Cost (@$0.12/kWh) |
|-----------|---------------|------------|--------------------------|
| Jetson Orin Nano | 10W avg | 88 kWh | $10.50 |
| NVMe SSD | 2W avg | 18 kWh | $2.15 |
| USB Audio | 0.5W avg | 4 kWh | $0.50 |
| **Total (24/7)** | **12.5W** | **110 kWh** | **$13.15/year** |

**Comparison**: A typical desktop PC (150W) costs ~$158/year to run 24/7.

---

**See Also:**
- [Environmental Constraints](environmental_constraints.md) - Operating conditions
- [Architecture Definition](../20_architecture/architecture_definition.md) - Multi-tier strategy
- [ADR-0003](../20_architecture/adrs/0003-multi-tier-hardware.md) - Multi-tier rationale
