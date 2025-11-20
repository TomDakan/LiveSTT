# scripts/setup_dev.py
import os
import secrets
from pathlib import Path


def setup() -> None:
    # 1. Resolve Paths (OS-agnostic)
    # This file is in /scripts, so parent.parent is the Project Root
    root_dir = Path(__file__).resolve().parent.parent

    print(f"📍 Project Root: {root_dir}")

    # 2. Define Directories to Create
    # (pathlib handles / vs \ automatically)
    dirs_to_create = [
        root_dir / "data" / "db",
        root_dir / "data" / "buffer",
        root_dir / "data" / "review",
        root_dir / "data" / "enrollment",
        root_dir / "secrets",
    ]

    print("📂 Creating directory structure...")
    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)
        print(f"   - Created: {d.relative_to(root_dir)}")

    # 3. Generate Secrets
    print("🔐 Checking secrets...")

    # Deepgram Key (Dummy)
    deepgram_file = root_dir / "secrets" / "deepgram_key.txt"
    if not deepgram_file.exists():
        print("   - Generating dummy Deepgram API Key...")
        deepgram_file.write_text("INSERT_REAL_DEEPGRAM_KEY_HERE", encoding="utf-8")
    else:
        print("   - Deepgram key exists. Skipping.")

    # Master Encryption Key (32 random bytes)
    master_key_file = root_dir / "secrets" / "master_encryption_key.bin"
    if not master_key_file.exists():
        print("   - Generating 32-byte Master Encryption Key...")
        # Replaces 'openssl rand 32'
        key_bytes = secrets.token_bytes(32)
        master_key_file.write_bytes(key_bytes)
    else:
        print("   - Master key exists. Skipping.")

    # 4. Permissions (Best Effort)
    # On Linux/Mac, this restricts access. On Windows, this is often ignored
    # or handled by ACLs, but os.chmod won't crash the script.
    try:
        if os.name == "posix":
            os.chmod(root_dir / "secrets", 0o700)
            os.chmod(deepgram_file, 0o600)
            os.chmod(master_key_file, 0o600)
            print("🔒 Restricted file permissions (Unix/Linux only).")
    except Exception as e:
        print(f"⚠️  Could not set permissions: {e}")

    print("\n✅ Setup Complete! You can now run: docker-compose up")


if __name__ == "__main__":
    setup()
