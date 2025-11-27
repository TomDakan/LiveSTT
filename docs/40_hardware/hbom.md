# Hardware Bill of Materials (HBOM)

## Overview
This document specifies the hardware components required for the v7.3 "Industrial Split-Brain" architecture.

> [!NOTE]
> All component models listed are **illustrative examples** to demonstrate viable options. They are not prescriptive recommendations or endorsements. Use equivalent components that meet the specified requirements (power, connectivity, performance).

---

## Tier 1: Production (Industrial x86)

### Core Components
| Component | Model | Quantity | Price (USD) | Purpose |
|-----------|-------|----------|-------------|---------|
| **Compute** | ASRock Industrial NUC BOX-N97 | 1 | $240 | Main compute (Fanless, Intel N97) |
| **Memory** | Crucial 16GB DDR4-3200 SODIMM | 1 | $35 | RAM (Single stick) |
| **Storage** | Transcend MTE712A 256GB NVMe | 1 | $65 | OS + "Black Box" (PLP protected) |
| **Audio Interface** | Focusrite Scarlett Solo 4th Gen | 1 | $140 | Low-noise preamp (-127dB EIN) |
| **Cabling** | USB-C to USB-C (Shielded) | 1 | $15 | Audio interface connection |

### Optional Components
| Component | Model | Quantity | Price (USD) | Purpose |
|-----------|-------|----------|-------------|---------|
| **UPS** | APC Back-UPS 425VA | 1 | $55 | Power conditioning (optional with PLP) |

**Total Cost (Tier 1)**: ~$495 (Hardware only)

---

## Tier 2: Desktop Development (x86_64)

### Core Components
| Component | Model | Quantity | Price (USD) | Purpose |
|-----------|-------|----------|-------------|---------|
| **Audio Interface** | Same as Tier 1 | 1 | $140 | USB audio input |

**Notes**:
- Uses developer's existing desktop/laptop
- Can run full stack (OpenVINO runs on CPU if no iGPU)

**Total Cost (Tier 2)**: ~$140 (Audio gear only)

---

## Tier 3: CI/CD & CPU-Only Development

### Core Components
| Component | Model | Quantity | Price (USD) | Purpose |
|-----------|-------|----------|-------------|---------|
| **Audio Interface** | Mock audio files (no hardware) | 0 | $0 | Testing with pre-recorded sermons |

**Notes**:
- Runs on GitHub Actions runners or developer laptops
- `identifier` service runs in CPU mode (slower but functional)

**Total Cost (Tier 3)**: $0

---

## Part Selection Rationale

### Why ASRock NUC BOX-N97?
- **Reliability**: Fanless design (no moving parts to fail)
- **Silence**: 0dB operation (critical for church sanctuary)
- **Performance**: Intel N97 (4C/4T) sufficient for OpenVINO inference
- **Watchdog**: Built-in hardware watchdog timer (ITE IT8xxx)
- **Cost**: $240 (vs $499 for Jetson)

### Why Transcend MTE712A?
- **PLP**: Power Loss Protection capacitors prevent data corruption
- **Endurance**: Industrial grade NAND
- **Reliability**: Essential for "Black Box" filesystem integrity

### Why Focusrite Scarlett Solo?
- **Noise Floor**: -127dB EIN (vs -90dB for cheap USB mics)
- **Quality**: "Clean Lab" quality audio improves biometric accuracy
- **Driverless**: Class-compliant USB audio (works with Linux/PipeWire)

---

## Supply Chain & Availability

| Component | Lead Time | Availability | Alternative |
|-----------|-----------|--------------|-------------|
| ASRock NUC N97 | 1-2 weeks | Newegg/Amazon | ASUS PN42 (N100) |
| Transcend NVMe | In stock | Mouser/DigiKey | Innodisk 3TE7 |
| Focusrite Solo | In stock | Music retailers | Motu M2 |

---

## Environmental Impact

| Component | Power (Watts) | Annual kWh | Annual Cost (@$0.12/kWh) |
|-----------|---------------|------------|--------------------------|
| NUC N97 | 10W avg | 88 kWh | $10.50 |
| NVMe SSD | 2W avg | 18 kWh | $2.15 |
| Audio Interface | 2.5W avg | 22 kWh | $2.60 |
| **Total (24/7)** | **14.5W** | **128 kWh** | **$15.36/year** |

**Comparison**: A typical desktop PC (150W) costs ~$158/year to run 24/7.

---

**See Also:**
- [Environmental Constraints](environmental_constraints.md) - Operating conditions
- [Architecture Definition](../20_architecture/architecture_definition.md) - Multi-tier strategy
- [ADR-0007](../20_architecture/adrs/0007-platform-pivot-x86.md) - Platform rationale
