# Threat Model (v8.0)

## 1. Overview
This document identifies security threats to the Live STT system (v8.0 Buffered Brain) and documents mitigations.

---

## 2. Assets & Risks

| Asset | Classification | Storage | Risk |
|-------|----------------|---------|------|
| **Voiceprints** | PII (Biometric) | `/data/lancedb` | HIGH |
| **Transcripts** | Sensitive | `/data/nats` | MEDIUM |
| **API Keys** | Credentials | Env Vars | HIGH |

---

## 3. Attack Surface

### 3.1 NATS Message Bus
- **Threat**: Unauthorized subscription to `transcript.raw` or `transcript.identity`.
- **Mitigation**:
    - NATS is isolated in `internal_overlay` network.
    - No external port exposure (except 8222 for monitoring, localhost only).

### 3.2 Physical Access (x86 NUC)
- **Threat**: Theft of device.
- **Mitigation**:
    - **Full Disk Encryption (LUKS)**: Data unreadable without passphrase/TPM.
    - **Secure Boot**: Prevents booting malicious OS.
    - **BIOS Password**: Prevents changing boot order.

### 3.3 Cloud Connection
- **Threat**: Interception of audio stream to Deepgram.
- **Mitigation**: TLS 1.3 (HTTPS/WSS) for all outbound traffic.

---

## 4. Threat Scenarios

### 4.1 "Evil Maid" Attack
**Scenario**: Attacker gains physical access to NUC in church AV rack.
**Defense**:
- BIOS Password prevents USB boot.
- Chassis intrusion switch (if supported) logs event.
- LUKS encryption prevents mounting drive on another machine.

### 4.2 NATS Injection
**Scenario**: Compromised container tries to inject fake identity events.
**Defense**:
- `identity-manager` validates `trace_id` correlation.
- Future: NATS 2.10 Auth (User/Pass per service).

---

## 5. Security Architecture

### 5.1 "Black Box" Integrity
The loopback filesystem (`/data/nats.img`) is mounted with `data=journal`.
- **Benefit**: Prevents corruption on power loss.
- **Security**: Can be unmounted and encrypted as a single file for transport.

### 5.2 Biometric Privacy
- **Crypto-Shredding**: Deleting the encryption key for archived audio renders it useless.
- **Vector Anonymity**: WeSpeaker embeddings cannot be easily reversed to raw audio.

---

**See Also:**
- [Biometric Policy](../30_data/biometric_policy.md)
- [HSI](../20_architecture/hsi.md)
