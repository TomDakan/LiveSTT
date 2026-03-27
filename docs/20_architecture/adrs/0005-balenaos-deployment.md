# Use BalenaOS for Edge Deployment

* **Status:** Accepted (hardware target updated — see ADR-0007)
* **Date:** 2025-11-19

---

## Context

The initial use case for the Live STT system will be deployed to edge hardware (Jetson Orin Nano) in a church environment with the following operational requirements:

1. **Remote management**: Deploy updates without physical access to devices
2. **Over-the-air updates**: Zero-downtime container updates
3. **Public URL**: HTTPS endpoint for remote access without static IP or VPN

The system must be **managed by non-technical staff** (church volunteers) while remaining **debuggable by remote developers**.

---

## Decision

We will use **BalenaOS** as the deployment platform for Tier 1 (Jetson Orin Nano) devices.

### Key Features Used
- **balenaCloud**: Fleet management dashboard
- **Public Device URL**: Auto-provisioned HTTPS endpoint (`<uuid>.balena-devices.com`)
- **Delta Updates**: Only changed layers pushed to device (saves bandwidth)
- **Supervisor**: Auto-restart containers, log aggregation
- **SSH Access**: Secure remote shell via balena CLI (`balena ssh <device-uuid>`)

### Deployment Workflow
```bash
# Developer pushes update
balena push live-stt-fleet

# BalenaCloud builds images, generates delta
# Supervisor pulls delta (~10MB vs ~500MB full image)
# Containers restarted with new version
# Public URL remains accessible during update
```

---

## Consequences

### Positive
- **Zero-config networking**: No port forwarding, no static IP, no DDNS
- **Built-in TPM support**: Balena integrates with Jetson's TPM 2.0 module
- **SSH tunneling**: Developers can debug live devices via `balena ssh` (no exposed SSH port)
- **Log aggregation**: All container logs viewable in balenaCloud dashboard
- **Immutable infrastructure**: Every deploy is a fresh container (no config drift)

### Negative
- **Vendor lock-in**: Migrating to vanilla Docker/Kubernetes requires rewriting deployment scripts
- **Internet dependency for updates**: Cannot push updates during internet outages (acceptable, updates are not urgent)
- **balenaCloud dependency**: If Balena goes down, cannot deploy new updates (existing devices unaffected)
- **Cost**: \$10/month per device after 10 devices (free tier: 10 devices)

### Risks and Mitigations
- **Risk**: Balena company shutdown
  - **Mitigation**: BalenaOS is open-source, can self-host balenaCloud replacement
- **Risk**: Supervisor bug causes boot loop
  - **Mitigation**: Balena has rollback mechanism, can revert to previous release
- **Risk**: Public URL exposes device to attacks
  - **Mitigation**: Ticket-based WebSocket auth ([M7](../../roadmap_draft.md#milestone-7)), rate limiting

---

## Alternatives Considered

### Alternative 1: Standard Docker + Portainer
**Pros**:
- No vendor lock-in
- Lower cost (free)

**Why rejected**:
- **No remote access solution**: Requires VPN or exposed SSH (security risk)
- **Manual updates**: Must SSH to each device, run `docker compose pull` manually
- **No fleet management**: Cannot push updates to 10+ devices simultaneously

### Alternative 2: Kubernetes (K3s on Jetson)
**Pros**:
- Industry-standard orchestration
- Rich ecosystem (Helm charts, operators)

**Why rejected**:
- **Overkill for single-device deployment**: K3s designed for clusters, not edge appliances
- **Resource overhead**: \~500MB RAM for control plane (Jetson only has 8GB total)
- **Complexity**: Requires Kubernetes expertise for troubleshooting

### Alternative 3: Ansible + Docker Compose
**Pros**:
- Open-source
- Flexible (can target any Linux host)

**Why rejected**:
- **No fleet visibility**: Must SSH to each device to check status
- **Playbook authoring**: Requires YAML expertise (higher barrier than `git push`)
- **No automatic rollback**: Failed deploy requires manual intervention

### Alternative 4: AWS IoT Greengrass
**Pros**:
- Native AWS integration
- Lambda@Edge support

**Why rejected**:
- **AWS lock-in**: Entire stack becomes AWS-dependent
- **Complexity**: Greengrass architecture is heavyweight (multiple daemons)
- **Cost**: Per-device pricing higher than Balena

---

## Amendment (ADR-0007, 2025-11-26)

**Hardware target changed from Jetson Orin Nano to ASRock Industrial NUC BOX-N97 (x86_64).**

BalenaOS fully supports x86_64 (`intel-nuc` device type), so this decision remains valid.
The TPM reference above no longer applies (NUC N97 uses the standard BalenaOS flow, not
Jetson-specific TPM integration). All other features — fleet management, delta updates,
public device URL, SSH tunnelling, log aggregation — apply unchanged.

### Data Persistence Across OTA Updates

BalenaOS provides a persistent `/data/` partition on the NVMe that survives container
updates. All stateful data **must** use named volumes mapped into `/data/`, not bind mounts:

| Data | Volume | Path |
|------|--------|------|
| NATS JetStream store | `nats_data` | `/data/nats` |
| Vocabulary & transcript SQLite DB | `db_data` | `/data/db` |
| LanceDB voiceprint store | `lancedb_data` | `/data/lancedb` |

Bind mounts (`./data/nats`) work for local development but are not suitable for production
as they are relative to the project directory and reset on each Balena deploy.

Vocabulary lists and enrolled voiceprints are **device-local** and survive software updates
but are not automatically replicated across the fleet. They must be backed up explicitly.

### Backup Strategy

Device-local persistent data (vocabulary, voiceprints) must be backed up separately from
the container images. The following strategy applies:

- **Local backup**: `POST /admin/backup` triggers a tar archive of `/data/db` and
  `/data/lancedb` downloadable via the admin UI or `just backup-device <uuid>`
- **Cloud backup**: architecture leaves the door open for periodic sync to object storage
  (S3/GCS/Azure Blob); not implemented in v8.0 but a `backup.destination` env var is
  reserved for this purpose

Audio data (`/data/nats`) is intentionally excluded from backup — it is transient by design
(1-hour retention window) and cannot be meaningfully restored out of order.

### Per-Device Environment Variables

Balena supports layered environment variable overrides:

1. **Fleet defaults**: set at fleet level in balenaCloud dashboard (e.g. a shared
   `DEEPGRAM_API_KEY` for a primary account)
2. **Device overrides**: individual devices can override any fleet variable (e.g. a church
   with its own Deepgram account sets `DEEPGRAM_API_KEY` at the device level)

This allows a single fleet definition to support multiple deployment sites with different
API credentials without modifying the image or repository.

See [ADR-0007](0007-platform-pivot-x86.md) for platform pivot rationale.

## References

- [ADR-0007](0007-platform-pivot-x86.md) - Platform pivot to x86 NUC
- [Balena Documentation](https://www.balena.io/docs/)
- [Deployment Runbooks](../../60_ops/runbooks.md) - Balena deploy procedures
