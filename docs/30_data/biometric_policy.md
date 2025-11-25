# Biometric Data Policy

## 1. Overview
This document defines policies and procedures for handling biometric data (voiceprints) in the Live STT system, ensuring compliance with biometric privacy laws including Illinois' Biometric Information Privacy Act (BIPA).

---

## 2. Regulatory Context

### 2.1 Applicable Laws
| Regulation | Jurisdiction | Key Requirements |
|------------|--------------|------------------|
| **BIPA** (740 ILCS 14/) | Illinois | Written consent, disclosure of retention policy, prohibition on sale |
| **GDPR** Article 9 | EU (if applicable) | Explicit consent for biometric processing, right to erasure |
| **CCPA** § 1798.140(b) | California | Disclosure of biometric data collection in privacy notice |

### 2.2 Scope
This policy applies to:
- **Voiceprints**: Audio embeddings extracted from enrollment samples via SpeechBrain ECAPA-TDNN model
- **Enrollment Audio**: Raw .wav files used to generate voiceprints

**Out of Scope**:
- Live audio streams (not stored)
- Transcripts (text only, not biometric)

---

## 3. Data Collection

### 3.1 Enrollment Process
1. **Admin initiates enrollment** via `/admin/enrollment` endpoint
2. **System displays consent form** with the following disclosures:
   - Purpose: "To identify you by name in live transcripts"
   - Storage: "Encrypted voiceprint stored locally on device"
   - Retention: "Until you request deletion"
   - No sale: "Your voiceprint will never be sold or shared with third parties"
3. **Speaker must explicitly consent** (checkbox)
4. **Speaker records enrollment audio** by reading the consent script aloud:
   ```
   "I, [NAME], consent to the collection of my voiceprint for the purpose 
   of identifying my speech in live transcripts. I understand that my 
   voiceprint will be stored locally on this device, encrypted, and will 
   not be sold or shared. I can request deletion at any time."
   ```
   - **Duration**: ~15 seconds (optimal for embedding extraction)
   - **Benefits**: Creates audio record of consent, ensures quality speech sample
5. **Voiceprint generated and encrypted** with per-file AES-256 key

### 3.2 Consent Requirements (BIPA § 15(b))
**Required Disclosures** (must be in writing):
- [x] Specific purpose for collecting biometric data
- [x] Length of retention period
- [x] Statement that data will not be sold

**Implementation**:
```html
<!-- In api-gateway enrollment UI -->
<form>
  <h2>Voiceprint Enrollment</h2>
  
  <p><strong>Purpose:</strong> We will use your voiceprint to label your speech in live transcripts with your name instead of "Speaker 0".</p>
  <p><strong>Retention:</strong> Your voiceprint will be stored until you request deletion via the admin dashboard.</p>
  <p><strong>Privacy:</strong> Your voiceprint is stored locally on this device (not in the cloud) and will never be sold or shared.</p>
  
  <label>
    <input type="checkbox" name="consent" required>
    I have read and agree to the biometric data collection policy.
  </label>
  
  <hr>
  
  <h3>Record Enrollment Sample</h3>
  <p>Please read the following statement aloud when you click "Record":</p>
  <blockquote id="enrollment-script">
    "I, [NAME], consent to the collection of my voiceprint for the purpose 
    of identifying my speech in live transcripts. I understand that my 
    voiceprint will be stored locally on this device, encrypted, and will 
    not be sold or shared. I can request deletion at any time."
  </blockquote>
  
  <button type="button" id="record-btn">Start Recording (15 seconds)</button>
  <button type="submit" disabled>Submit Enrollment</button>
</form>
```

### 3.3 Data Minimization
- **Only voice recordings** (no video, photos, or other biometric modalities)
- **Single enrollment sample** per speaker (no continuous collection)
- **Embedding-only storage** after enrollment (raw audio can be deleted after embedding extraction)

---

## 4. Data Storage

### 4.1 Encryption
| Data Type | Encryption Method | Key Storage |
|-----------|-------------------|-------------|
| Enrollment audio | AES-256-GCM per-file | SQLite `voiceprint_enrollment.encryption_key` |
| Voiceprint embedding | AES-256-GCM (same key as audio) | SQLite `voiceprint_enrollment.encryption_key` |
| File encryption keys | Encrypted with master key | TPM-sealed (Tier 1) or `/config/master.key` (Tier 2/3) |

### 4.2 Access Control
| Role | Can Enroll | Can View Embeddings | Can Delete |
|------|-----------|-------------------|-----------|
| **Admin** | Yes | No (embeddings are binary, not human-readable) | Yes |
| **identifier Service** | No | Yes (decrypts to perform matching) | No |
| **Other Services** | No | No | No |

### 4.3 Physical Security
- **Tier 1 (Jetson + BalenaOS)**: Full-disk encryption (LUKS), Secure Boot, TPM key sealing
- **Tier 2/3 (Docker Compose)**: User responsible for securing `/config/master.key`

---

## 5. Data Usage

### 5.1 Permitted Uses
- **Speaker identification**: Matching live audio to enrolled voiceprints
- **Transcript labeling**: Replacing "Speaker 0" with speaker name in UI

### 5.2 Prohibited Uses
- **Sale or monetization**: Voiceprints shall NEVER be sold, licensed, or shared for profit (BIPA § 15(c))
- **Third-party sharing**: No voiceprints sent to Deepgram, BalenaCloud, or any external service
- **Facial recognition**: Voiceprints shall not be cross-referenced with photos or video
- **Law enforcement**: No access to voiceprints for surveillance or investigation (without warrant)

---

## 6. Data Retention

### 6.1 Retention Period
**Indefinite (consent-based)**: Voiceprints stored until speaker requests deletion

### 6.2 Automatic Deletion Triggers
- Speaker submits deletion request via admin dashboard
- Device is decommissioned (all data wiped)

### 6.3 No Retention After Purpose Fulfilled
If speaker is no longer active (e.g., staff member leaves church), admin should delete voiceprint.

---

## 7. Right to Erasure (GDPR Article 17)

### 7.1 Deletion Procedure
1. **Speaker requests deletion** (verbal or written request to admin)
2. **Admin navigates** to `/admin/voiceprints`
3. **Admin clicks "Delete"** next to speaker name
4. **System performs crypto-shredding**:
   - Deletes `voiceprint_enrollment.encryption_key` from database
   - Encrypted file remains on disk but is **permanently unrecoverable** (even with master key)
5. **Deletion confirmed** in UI

### 7.2 Crypto-Shredding Implementation
```python
# api-gateway endpoint: DELETE /admin/voiceprint/{speaker_id}
def delete_voiceprint(speaker_id: str):
    db.execute(
        "DELETE FROM voiceprint_enrollment WHERE speaker_id = ?",
        (speaker_id,)
    )
    # File /data/enrollment/{speaker_id}.wav.enc still exists but cannot be decrypted
    # Optionally: os.remove(file_path) for immediate disk reclamation
```

### 7.3 Deletion Verification
Admin can verify deletion by:
- Confirming speaker no longer appears in `/admin/voiceprints` list
- Checking logs for `DELETE FROM voiceprint_enrollment` SQL query

---

## 8. Breach Notification

### 8.1 Breach Definition
A breach occurs if:
- Encrypted voiceprint file AND encryption key are both exfiltrated
- Master key is compromised (allowing decryption of all file keys)

### 8.2 Notification Timeline (GDPR Article 33/34)
- **72 hours**: Notify data protection authority (if EU users)
- **Without undue delay**: Notify affected individuals

### 8.3 Notification Content
- Description of breach (e.g., "Device theft, master key unsealed")
- Potential consequences (e.g., "Voiceprints may be used for impersonation")
- Mitigation measures (e.g., "All voiceprints re-encrypted with new key")

---

## 9. Audit Trail

### 9.1 Logged Events
| Event | Log Location | Retention |
|-------|--------------|-----------|
| Voiceprint enrollment | `voiceprint_enrollment.enrolled_at` | Indefinite |
| Consent provided | `voiceprint_enrollment.consented` | Indefinite |
| Voiceprint deletion | Application logs | 30 days |
| Identification match | `identity.event` ZMQ topic (not persisted) | Session only |

### 9.2 Audit Queries
```sql
-- List all enrolled speakers
SELECT speaker_id, enrolled_at, consented FROM voiceprint_enrollment;

-- Verify consent flag
SELECT speaker_id FROM voiceprint_enrollment WHERE consented = 0;  -- Should return empty

-- Check deletion history (requires app logs)
grep "DELETE FROM voiceprint_enrollment" /var/log/api-gateway.log
```

---

## 10. Third-Party Processors

### 10.1 SpeechBrain Model
- **Processing**: On-device (no data sent to SpeechBrain authors)
- **Model License**: Apache 2.0 (permissive, no data sharing obligations)

### 10.2 BalenaCloud
- **Data Transmitted**: Docker images, logs (does NOT include voiceprints or encryption keys)
- **Access**: Balena employees cannot access `/data/enrollment/` (encrypted at rest)

---

## 11. Policy Review

**Frequency**: Annually or upon regulatory changes  
**Owner**: System Administrator (USER)  
**Next Review**: 2026-11-20

---

**See Also:**
- [DPIA](../70_legal/dpia.md) - Data Protection Impact Assessment (deferred to production)
- [Threat Model](../20_architecture/threat_model.md) - Security safeguards for voiceprints
- [Data Dictionary](data_dictionary.md) - Voiceprint database schema
