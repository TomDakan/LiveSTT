#!/bin/bash

# ==============================================================================
# SETUP_DEV.SH
# bootstraps the local environment for the STT Kiosk Monorepo.
# Usage: ./scripts/setup_dev.sh
# ==============================================================================

set -e # Exit immediately if a command exits with a non-zero status.

# 1. Get the Project Root (assuming script is in /scripts)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📍 Project Root identified as: $PROJECT_ROOT"

# 2. Create Data Volume Directories (Mocking NVMe storage)
echo "📂 Creating data volume structure..."
mkdir -p data/db
mkdir -p data/buffer
mkdir -p data/review
mkdir -p data/enrollment

# 3. Create Secrets Directory
echo "🔐 Creating secrets directory..."
mkdir -p secrets

# 4. Generate Dummy Secrets (if they don't exist)
# NOTE: These are for local dev only. Production uses real keys.

# Deepgram Key
if [ ! -f secrets/deepgram_key.txt ]; then
    echo "   - Generating dummy Deepgram API Key..."
    echo "INSERT_REAL_DEEPGRAM_KEY_HERE" > secrets/deepgram_key.txt
else
    echo "   - Deepgram key already exists. Skipping."
fi

# Master Encryption Key (32 bytes for AES-256)
if [ ! -f secrets/master_encryption_key.bin ]; then
    echo "   - Generating random 32-byte Master Encryption Key..."
    openssl rand -out secrets/master_encryption_key.bin 32
else
    echo "   - Master key already exists. Skipping."
fi

# 5. Set Permissions
# Ensure strictly private permissions for secrets
chmod 700 secrets
chmod 600 secrets/*

echo "✅ Setup Complete! You can now run:"
echo "   docker-compose up --build"
