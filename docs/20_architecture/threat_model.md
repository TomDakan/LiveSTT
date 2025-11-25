# Threat Model

## 1. Overview
This document identifies security threats to the Live STT system and documents mitigations. The system handles sensitive biometric data (voiceprints) and potentially sensitive transcript content, operating in an edge deployment with intermittent internet connectivity.

## 2. Assets

| Asset | Classification | Storage Location | Risk Impact |
|-------|----------------|------------------|-------------|
| **Voiceprints** | PII (Biometric) | `/data/enrollment/*.enc` | HIGH - Identity theft risk |
| **Audio Snippets** | PII (Voice recordings) | `/data/review/*.enc` | HIGH - Privacy violation |
| **Transcripts** | Sensitive | In-memory, logged to `/data/config.db` | MEDIUM - Content disclosure |
| **API Keys** | Credentials | Environment variables | HIGH - Service compromise |
| **Encryption Keys** | Secrets | `/config/master.key` or TPM | CRITICAL - Data exposure |

## 3. Threat Actors

| Actor | Motivation | Capability | Likelihood |
|-------|-----------|------------|------------|
| **Opportunistic Attacker** | Financial gain | Low (physical access) | LOW |
| **Insider Threat** | Curiosity, malice | High (authorized access) | MEDIUM |
| **Nation State** | Surveillance | Very High | Very LOW (out of threat model scope) |

## 4. Attack Surface

### 4.1 Network Interfaces
| Interface | Exposure | Threat | Mitigation |
|-----------|----------|--------|------------|
| **Public Device URL** (Balena) | Internet | Unauthorized access | Ticket-based WebSocket auth ([M7](../roadmap_draft.md#milestone-7)) |
| **Docker Internal Network** | Container-to-container | Lateral movement | No host network mode, ZMQ broker isolation |
| **Deepgram API** (WSS) | Internet | MITM, credential theft | TLS 1.3, API key rotation |

### 4.2 Physical Access
| Vector | Threat | Mitigation |
|--------|--------|------------|
| **Device Theft** | Data exfiltration | Full-disk encryption (LUKS), TPM key sealing (Tier 1) |
| **USB/HDMI Access** | Boot from external media | Secure Boot (BalenaOS), BIOS password |
| **SD Card Removal** | Offline attack | Encrypted volumes, TPM-sealed keys cannot be decrypted off-device |

### 4.3 Software Supply Chain
| Vector | Threat | Mitigation |
|--------|--------|------------|
| **Compromised Docker Images** | Backdoor, malware | Pull from trusted registries (Docker Hub official, nvcr.io), SBOM scanning |
| **Malicious Dependencies** | Supply chain attack | `safety` checks in CI, pinned versions in `pdm.lock` |

## 5. Threat Scenarios

### 5.1 PII Exfiltration via Stolen Device
**Attack**: Attacker steals Jetson device, attempts to extract voiceprints from `/data/enrollment/`.

**Mitigations**:
1. **Full-Disk Encryption** (LUKS): Requires passphrase at boot
2. **Per-File Encryption** (AES-256): `/data/enrollment/*.enc` uses separate encryption key
3. **TPM Key Sealing** (Tier 1): Master key sealed to TPM, cannot be extracted without device hardware

**Residual Risk**: If attacker has both physical device AND can boot it (compromise secure boot), they can access unencrypted data in RAM. **Mitigation**: Memory encryption (future enhancement).

### 5.2 Unauthorized Access to Admin Dashboard
**Attack**: Attacker gains access to admin UI at `https://<device-url>:8001/admin`.

**Mitigations**:
1. **Network Isolation**: Admin port (8001) not exposed to internet, only accessible via local network or VPN
2. **Authentication**: SQLAdmin requires login (credentials in environment variables)
3. **Audit Logging**: All admin actions logged to `/data/config.db`

**Residual Risk**: Insider with local network access can brute-force weak passwords. **Mitigation**: Enforce strong passwords, add MFA (future enhancement).

### 5.3 Deepgram API Key Compromise
**Attack**: Attacker extracts `DEEPGRAM_API_KEY` from environment or logs.

**Mitigations**:
1. **Environment Variables**: Key never written to disk (except in `.env` file, which is gitignored)
2. **Log Sanitization**: Ensure no services log the full API key
3. **Key Rotation**: Manual rotation procedure in runbooks

**Residual Risk**: Attacker with `docker inspect` access can read environment. **Mitigation**: Use Docker Secrets (future enhancement).

### 5.4 Malicious Audio Injection
**Attack**: Attacker replaces `audio-producer` with malicious container that injects crafted audio to trigger vulnerabilities in `stt-provider` or `identifier`.

**Mitigations**:
1. **Image Signing**: Balena fleet uses signed images
2. **Immutable Infrastructure**: Services run as read-only containers where possible
3. **Input Validation**: `stt-provider` validates PCM format before streaming to Deepgram

**Residual Risk**: Zero-day in Deepgram SDK. **Mitigation**: Keep dependencies up-to-date via Dependabot.

## 6. Security Architecture

### 6.1 Crypto-Shredding
When a voiceprint or audio snippet is deleted:
1. Delete the per-file encryption key from `config.db`
2. The encrypted file becomes permanently unrecoverable (even with master key)

```python
# stt-provider saves low-confidence snippet
file_key = os.urandom(32)
encrypt_file(audio_data, file_key)
db.save_key(snippet_id, file_key)

# Admin deletes snippet
db.delete_key(snippet_id)  # Crypto-shredding complete
```

### 6.2 TPM Key Sealing (Tier 1)
```python
# Master key sealed to TPM PCR registers (boot state)
master_key = tpm2_unseal(pcr=[0, 7])  # Only succeeds if boot state unchanged
file_key = db.get_key(snippet_id)
plaintext = decrypt(ciphertext, master_key, file_key)
```

**Protection**: Key cannot be unsealed if:
- Secure Boot chain is compromised
- Firmware is modified
- Device is running a different OS

### 6.3 Container Isolation
```yaml
services:
  stt-provider:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only if binding privileged ports
```

**Additional Hardening** (future):
- AppArmor profiles
- Read-only root filesystem
- Non-root user (UID 1000)

## 7. Compliance Considerations

| Regulation | Applicability | Key Requirements | Implementation |
|------------|---------------|------------------|----------------|
| **GDPR** (if EU users) | Possible | Right to erasure, data minimization | Crypto-shredding, optional voiceprint enrollment |
| **CCPA** (California) | Possible | Disclosure of data collection | Privacy policy, consent UI |
| **BIPA** (Illinois) | Yes (if IL church) | Written consent for biometrics | Enrollment UI requires explicit consent |

**See**: [DPIA](../70_legal/dpia.md) for full Data Protection Impact Assessment (deferred to production).

## 8. Incident Response

### 8.1 Device Compromise
1. **Immediate**: Revoke Balena device access, rotate Deepgram API key
2. **Forensics**: Extract logs from `/data/config.db`, analyze Docker container state
3. **Remediation**: Reflash device with known-good image, restore from backup

### 8.2 Data Breach
1. **Assessment**: Determine if encrypted files were accessed (check file access logs)
2. **Notification**: If PII exfiltration confirmed, notify affected individuals within 72 hours (GDPR)
3. **Containment**: Invalidate compromised encryption keys via crypto-shredding

## 9. Security Roadmap

| Milestone | Security Feature | Status |
|-----------|------------------|--------|
| M7 | Ticket-based WebSocket auth | Planned |
| M7 | Master key management (TPM/user-provided) | Planned |
| M9 | Encrypted snippet streaming | Planned |
| M12 | Voiceprint enrollment (encrypted storage) | Planned |
| Post-M13 | AppArmor profiles, read-only containers | Future |
| Post-M13 | Multi-factor authentication for admin | Future |

---

**See Also:**
- [System Design](../system_design.md) - Section 6 (Security Architecture)
- [Biometric Policy](../30_data/biometric_policy.md) - Voiceprint handling procedures
- [Secrets Manifest](../60_ops/secrets_manifest.md) - Credential inventory
