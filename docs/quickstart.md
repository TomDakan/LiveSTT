# Quickstart Guide (v7.3)

## Overview
This guide will help you deploy the Live STT system on the **Tier 1 (Industrial x86)** platform or a **Tier 2 (Desktop)** environment for testing.

> [!IMPORTANT]
> This guide is for **end-users and administrators**. If you are a developer looking to contribute code, please see [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## Prerequisites

### Hardware
- **Compute**: ASRock Industrial NUC BOX-N97 (Tier 1) OR Desktop PC (Tier 2)
- **Audio**: Focusrite Scarlett Solo (or similar USB interface)
- **Network**: Ethernet connection (preferred)

### Software Accounts
- **Deepgram**: [Sign up](https://console.deepgram.com) and create an API Key.
- **BalenaCloud** (Tier 1 only): [Sign up](https://dashboard.balena-cloud.com) for a free account.

---

## Option A: Production Deployment (Industrial NUC + Balena)

### 1. Create Fleet
1. Log in to BalenaCloud.
2. Click **"Create Fleet"**.
3. Name: `live-stt-production`.
4. Device Type: **Generic x86_64 (GPT)**.

### 2. Flash Device
1. Click **"Add Device"** in your new fleet.
2. Download the BalenaOS image (Development edition recommended for initial setup).
3. Flash to USB Drive using [BalenaEtcher](https://www.balena.io/etcher/).
4. Insert USB into NUC, power on, and boot from USB (F11/F12).
5. Install BalenaOS to internal NVMe when prompted.

### 3. Configure Variables
In the Balena Dashboard, go to **Variables** and add:
- `DEEPGRAM_API_KEY`: `<your-deepgram-key>`
- `LOG_LEVEL`: `INFO`

### 4. Deploy Code
Install [Balena CLI](https://github.com/balena-io/balena-cli) on your computer:
```bash
# Login
balena login

# Push code
git clone https://github.com/yourusername/live-stt.git
cd live-stt
balena push live-stt-production
```

### 5. Verify
Visit the device's public URL (enable in Balena dashboard) or local IP: `https://<device-ip>:8000`.

---

## Option B: Local Testing (Docker Compose)

### 1. Install Docker
Ensure [Docker Desktop](https://www.docker.com/products/docker-desktop/) is installed and running.

### 2. Clone & Configure
```bash
git clone https://github.com/yourusername/live-stt.git
cd live-stt

# Create environment file
cp .env.example .env
```

### 3. Set API Key
Edit `.env` and paste your key:
```ini
DEEPGRAM_API_KEY=a1b2c3d4...
```

### 4. Run
```bash
docker compose up
```

### 5. Access
Open browser to `http://localhost:8000`.

---

## Next Steps

- **[Connect Audio](40_hardware/assembly_guide.md)**: Setup your Focusrite interface.
- **[Operations](60_ops/runbooks.md)**: Learn how to manage the system.
- **[Troubleshooting](60_ops/runbooks.md#10-troubleshooting-service-crashes)**: Fix common issues.
