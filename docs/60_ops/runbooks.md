# Runbooks / SOPs

## Incident: TPM Failure
**Trigger:** Log message "TPM Unseal Failed"
**Severity:** High

### Steps
1. Reboot device.
2. If persistent, clear PCR registers:
   ```bash
   tpm2_clear
   ```
3. Re-provision keys.
