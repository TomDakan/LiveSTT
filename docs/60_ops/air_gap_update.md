# Air-Gap Update Procedure

## Prerequisites
- Secure USB Drive (Encrypted)
- Update Artifact (`update.tar.gz`)

## Steps
1. Insert USB drive into port.
2. Mount drive:
   ```bash
   mount /dev/sda1 /mnt/usb
   ```
3. Run update script:
   ```bash
   /mnt/usb/update.sh
   ```
4. Verify checksum.
