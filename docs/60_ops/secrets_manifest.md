# Secrets Manifest

## Overview
This document catalogs all secrets, credentials, and encryption keys used in the Live STT system, including storage locations, rotation policies, and access controls.

---

## 1. Secrets Inventory

| Secret ID | Type | Purpose | Required Tier | Rotation Period |
|-----------|------|---------|---------------|-----------------|
| **DEEPGRAM_API_KEY** | API Key | Cloud STT service | All | 90 days |
| **ENCRYPTION_MASTER_KEY** | AES-256 Key | Encrypt per-file keys | Tier 2/3 | 365 days |
| **TPM_SEALED_KEY** | AES-256 Key | Encrypt per-file keys | Tier 1 | Never (sealed to hardware) |
| **ADMIN_PASSWORD** | Password | Admin dashboard access | All | 180 days |
| **WEBSOCKET_SECRET** | JWT Secret | WebSocket ticket signing | All (M7+) | 90 days |
| **DB_ENCRYPTION_KEY** | AES-256 Key | Encrypt sensitive DB columns | Future | 365 days |

---

## 2. Secret Storage

### Tier 1 (Balena)
| Secret | Storage Location | Access Method | Encryption at Rest |
|--------|------------------|---------------|-------------------|
| **DEEPGRAM_API_KEY** | Balena environment variables | `os.getenv("DEEPGRAM_API_KEY")` | ✅ (Balena Vault) |
| **TPM_SEALED_KEY** | TPM 2.0 PCR registers | `tpm2_unseal(pcr=[0,7])` | ✅ (Hardware-sealed) |
| **ADMIN_PASSWORD** | Balena environment variables | `os.getenv("ADMIN_PASSWORD")` | ✅ (Balena Vault) |
| **WEBSOCKET_SECRET** | Balena environment variables | `os.getenv("WEBSOCKET_SECRET")` | ✅ (Balena Vault) |

### Tier 2/3 (Docker Compose)
| Secret | Storage Location | Access Method | Encryption at Rest |
|--------|------------------|---------------|-------------------|
| **DEEPGRAM_API_KEY** | `.env` file (gitignored) | `os.getenv("DEEPGRAM_API_KEY")` | ❌ (User responsibility) |
| **ENCRYPTION_MASTER_KEY** | `/config/master.key` | Read from file | ❌ (User responsibility) |
| **ADMIN_PASSWORD** | `.env` file | `os.getenv("ADMIN_PASSWORD")` | ❌ (User responsibility) |

**Recommendation (Tier 2/3)**: Use Docker Secrets for production deployments
```bash
echo "<api-key>" | docker secret create deepgram_api_key -
```

---

## 3. Secret Generation

### DEEPGRAM_API_KEY
**Generation**:
1. Sign up at https://console.deepgram.com
2. Navigate to "API Keys"
3. Click "Create New Key"
4. Copy key (displayed once)

**Format**: `a1b2c3d4e5f6...` (64-character hex string)

### ENCRYPTION_MASTER_KEY (Tier 2/3)
**Generation**:
```bash
# Generate 256-bit random key
openssl rand -hex 32 > /config/master.key
chmod 600 /config/master.key
```

**Format**: 64-character hex string (32 bytes)

### TPM_SEALED_KEY (Tier 1)
**Generation** (automatic on first boot):
```bash
# Performed by Balena OS provisioning script
tpm2_createprimary -C o -g sha256 -G rsa -c primary.ctx
tpm2_create -C primary.ctx -g sha256 -G keyedhash \
    -r key.priv -u key.pub -I /dev/urandom
tpm2_load -C primary.ctx -u key.pub -r key.priv -c key.ctx
tpm2_evictcontrol -C o -c key.ctx 0x81000001  # Persist to NV
```

**Format**: Binary blob (not human-readable)

### ADMIN_PASSWORD
**Generation**:
```bash
# Generate strong random password
openssl rand -base64 24
# Example output: "Xk9J2mN8pL4qR7sT3vW6yZ1a"
```

**Requirements**:
- Minimum 16 characters
- Mix of uppercase, lowercase, numbers, symbols

### WEBSOCKET_SECRET (M7+)
**Generation**:
```bash
openssl rand -hex 32
```

**Format**: 64-character hex string

---

## 4. Secret Access Matrix

| Secret | Service | Permission | Why Needed |
|--------|---------|------------|------------|
| **DEEPGRAM_API_KEY** | stt-provider | Read | Connect to Deepgram WSS |
| **ENCRYPTION_MASTER_KEY** | api-gateway | Read | Decrypt per-file keys |
| **ENCRYPTION_MASTER_KEY** | stt-provider | Read | Encrypt audio snippets |
| **ENCRYPTION_MASTER_KEY** | identifier | Read | Decrypt voiceprints |
| **ADMIN_PASSWORD** | api-gateway | Read | Verify admin login |
| **WEBSOCKET_SECRET** | api-gateway | Read | Sign/verify JWT tickets |
| **TPM_SEALED_KEY** | api-gateway | Read | Unseal master key |

**Principle of Least Privilege**: No service has access to secrets it doesn't need

---

## 5. Secret Rotation Procedures

### Rotating DEEPGRAM_API_KEY
**Trigger**: Every 90 days, or on suspected compromise

**Steps**:
1. Generate new key in Deepgram console
2. Update environment variable (see [Runbooks](runbooks.md#7-rotating-deepgram-api-key))
3. Restart `stt-provider` service
4. Verify connectivity in logs
5. Revoke old key in Deepgram console

**Downtime**: ~30 seconds

### Rotating ENCRYPTION_MASTER_KEY (Tier 2/3)
**Trigger**: Every 365 days, or on suspected compromise

**⚠️ WARNING**: This requires **re-encrypting all existing files**

**Steps**:
```bash
# 1. Stop all services
docker compose down

# 2. Generate new master key
openssl rand -hex 32 > /config/master.key.new

# 3. Re-encrypt all per-file keys in database
python scripts/rotate_master_key.py \
    --old /config/master.key \
    --new /config/master.key.new

# 4. Replace master key
mv /config/master.key /config/master.key.old
mv /config/master.key.new /config/master.key

# 5. Restart services
docker compose up -d

# 6. Verify (test voiceprint decryption)
# 7. Delete old key
shred -u /config/master.key.old
```

**Downtime**: ~5 minutes

### Rotating TPM_SEALED_KEY (Tier 1)
**Not recommended**: TPM key is sealed to hardware and boot state. Rotation requires reflashing entire device.

**Alternative**: If compromise suspected, wipe device and start fresh.

### Rotating ADMIN_PASSWORD
**Trigger**: Every 180 days, or on suspected compromise

**Steps**:
1. Generate new password
2. Update `ADMIN_PASSWORD` environment variable
3. Restart `api-gateway` service
4. Verify login with new password

**Downtime**: None (admin dashboard only)

---

## 6. Secret Leak Detection

### Pre-Commit Hook (Git)
```bash
# Install pre-commit framework
pip install pre-commit

# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

**Excluded Patterns**:
- `.env.example` (placeholder values only)
- `test_fixtures/` (fake keys for testing)

### Continuous Monitoring
```bash
# Scan codebase for hardcoded secrets
docker run --rm -v $(pwd):/src trufflesecurity/trufflehog git file:///src
```

**CI/CD Integration**: Fails build if secrets detected

---

## 7. Secret Compromise Response

### DEEPGRAM_API_KEY Leak
**Impact**: Unauthorized STT usage (cost escalation)

**Response**:
1. Immediately revoke key in Deepgram console
2. Generate new key and rotate (see above)
3. Review Deepgram usage logs for anomalies
4. Enable rate limiting on new key

### ENCRYPTION_MASTER_KEY Leak
**Impact**: All encrypted files can be decrypted

**Response**:
1. **If backups exist**: Reflash device, restore from backup with new key
2. **If no backups**: Rotate master key (see above)
3. **If voiceprints compromised**: Notify affected speakers (GDPR/BIPA requirement)

### TPM_SEALED_KEY Leak
**Impact**: Minimal (key cannot be unsealed without physical device + secure boot)

**Response**: No action required (key is hardware-bound)

---

## 8. Secret Sharing (Team Access)

### Development Secrets (Tier 3)
**Storage**: **1Password** or **BitWarden** shared vault

**Access**:
- Deepgram API key: Read-only, shared with all developers
- Admin password: Development instance only (not production)

### Production Secrets (Tier 1)
**Storage**: Balena environment variables (admin access only)

**Access**:
- Only system administrator (USER)
- No shared credentials

**Audit Trail**: Balena logs all environment variable changes

---

## 9. Secrets in Logs

### Log Sanitization Rules
```python
# api-gateway logging filter
import logging
import re

class SanitizeSecretsFilter(logging.Filter):
    def filter(self, record):
        # Redact API keys
        record.msg = re.sub(
            r'DEEPGRAM_API_KEY=[\w]{64}',
            'DEEPGRAM_API_KEY=***REDACTED***',
            str(record.msg)
        )
        return True

logging.getLogger().addFilter(SanitizeSecretsFilter())
```

**Never Logged**:
- Full API keys (only first 8 characters: `a1b2c3d4...`)
- Encryption keys (never referenced in logs)
- Admin passwords (only hashed values)

---

## 10. Compliance

| Regulation | Requirement | Implementation |
|------------|-------------|----------------|
| **PCI DSS** | No plaintext secrets in logs | Log sanitization filter |
| **GDPR** | Encryption key management | Per-file keys, crypto-shredding |
| **BIPA** | Biometric data security | TPM sealing, voiceprint encryption |

---

**See Also:**
- [Threat Model](../20_architecture/threat_model.md) - Secret compromise scenarios
- [Biometric Policy](../30_data/biometric_policy.md) - Voiceprint encryption procedures
- [Runbooks](runbooks.md) - Secret rotation procedures
