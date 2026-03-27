# Biometric Data Policy (v8.0)

## 1. Overview
This document defines policies for handling biometric data (voiceprints) in the Live STT system (v7.3), ensuring compliance with BIPA and GDPR.

---

## 2. Scope
- **Voiceprints**: 256-dimensional vectors (WeSpeaker ResNet34) stored in LanceDB.
- **Enrollment Audio**: Raw .wav files (encrypted) used for re-enrollment.

---

## 3. Data Storage

### 3.1 Vector Storage (LanceDB)
- **Location**: `/data/lancedb`
- **Format**: LanceDB Table (`voiceprints`)
- **Encryption**: Volume-level encryption (LUKS) on the physical disk.

### 3.2 Backup Strategy ("Black Box")
- **Mechanism**: LanceDB snapshots are periodically synced to the "Black Box" loopback filesystem (`/data/nats`).
- **Purpose**: Disaster recovery only.

### 3.3 Physical Security (Tier 1 - Industrial NUC)
- **Full Disk Encryption**: LUKS enabled on BalenaOS.
- **Secure Boot**: Enabled in BIOS.
- **TPM**: Keys sealed to TPM 2.0 module.

---

## 4. Enrollment Process

1.  **Consent**: User must explicitly consent via UI checkbox.
2.  **Recording**: 15-second audio sample reading consent script.
3.  **Processing**:
    - Audio -> WeSpeaker -> Vector (256-float array).
    - Vector -> LanceDB.
    - Audio -> Encrypted Archive (AES-256).

---

## 5. Data Retention & Deletion

### 5.1 Retention
- **Voiceprints**: Indefinite (until revocation).
- **Transcripts**: 30 days (rolling deletion).

### 5.2 Right to Erasure
- **Action**: Admin clicks "Delete" in Dashboard.
- **Technical**:
    1.  `DELETE FROM voiceprints WHERE id = 'Alice'`
    2.  Crypto-shredding of archived audio key.
    3.  Vacuum LanceDB to remove vector data.

---

**See Also:**
- [Data Dictionary](data_dictionary.md)
- [Threat Model](../20_architecture/threat_model.md)
