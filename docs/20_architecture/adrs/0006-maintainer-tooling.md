# Maintainer Tooling vs. End-User Admin Interface

* **Status:** Accepted
* **Date:** 2025-11-24
* **Deciders:** Tom Dakan

---

## Context

The Live STT system requires two distinct categories of administrative functionality:

1. **End-User Operations** (M8: Admin Dashboard)
   - Routine management (PhraseSet editing, user enrollment)
   - Polished UI suitable for non-technical operators
   - Production-ready, stable interfaces

2. **Developer/Maintainer Operations** (This ADR)
   - Deployment validation (thermal burn-in, network resilience tests)
   - Hardware diagnostics (GPU availability, disk space, temperature monitoring)
   - Quality assurance (running Gold Standard regression tests manually)
   - Troubleshooting utilities (log analysis, service health checks)

**Problem Statement**: Developer/maintainer operations are too technical for the polished admin UI, but too important to leave ad-hoc or undocumented. We need a formalized approach to maintainer tooling.

---

## Decision

We will implement a **two-tier administrative interface strategy**:

### Tier 1: End-User Admin Dashboard (M8)
- **Technology**: SQLAdmin integrated into `api-gateway`
- **Access**: Local network only (`:8000/admin`)
- **Audience**: Church staff, operators, admins
- **Examples**: PhraseSet editor, speaker enrollment, basic status

### Tier 2: Maintainer/DevOps Tools (M8.5)
- **Technology**: `just` command recipes + optional barebones web dashboard
- **Access**:
  - **Primary**: CLI via Balena SSH (`balena ssh <device-uuid>`)
  - **Optional**: Simple web UI on port `:9000` (disabled by default in production)
- **Audience**: System administrators, deployers, troubleshooters
- **Examples**: Hardware burn-in, WER regression tests, log aggregation

---

## Architecture

### Phase 1: CLI-First (M8.5.1)
Extend `justfile` with maintainer commands:

```bash
# Deployment validation
just burn-in-test          # 60-min stress-ng + temp monitoring
just validate-network      # 10-min offline buffer test
just validate-gold-corpus  # Run WER regression test

# Diagnostics
just health-check          # Check all services + hardware
just gpu-info              # Verify GPU availability (Tier 1/2)
just disk-usage            # Report /data volume usage

# Troubleshooting
just logs-aggregate        # Tail all service logs
just reset-buffers         # Clear /data/buffer (troubleshooting)
```

**Access Method**:
```bash
balena ssh <device-uuid>
cd /app  # Application directory
just burn-in-test
```

### Phase 2: Optional Web Dashboard (M8.5.2 - Future)
If CLI proves insufficient, add minimal Flask/FastAPI service:

```yaml
devops-dashboard:
  build: ./services/devops-dashboard
  ports:
    - "9000:9000"  # Separate port from admin UI
  environment:
    - ENABLE_DASHBOARD=false  # Disabled by default
```

**Features**:
- Real-time burn-in progress bars
- Live log tailing (web-based `docker logs -f`)
- One-click regression test execution
- Hardware metrics visualization (temp, GPU util)

**Security**: Only runs when explicitly enabled, local network only

---

## Consequences

### Positive
- **Clear separation of concerns**: Routine ops vs. deployment/diagnostics
- **Low initial complexity**: CLI-first approach requires minimal new code
- **Balena compatibility**: SSH access is native to BalenaOS
- **Flexibility**: Can add web dashboard later if needed
- **Documentation**: Commands are self-documenting via `just --list`

### Negative
- **Requires CLI familiarity**: Deployers need SSH comfort (mitigated by good docs)
- **Two admin interfaces**: Potential confusion (mitigated by clear naming: "Admin UI" vs. "DevOps CLI")
- **Balena-specific**: `just` commands assume Balena environment (acceptable for Tier 1 focus)

### Risks and Mitigations
- **Risk**: Less technical deployers struggle with CLI
  - **Mitigation**: Provide step-by-step runbooks, consider web dashboard in M8.5.2
- **Risk**: `just` commands not portable to non-Balena environments
  - **Mitigation**: Keep commands simple, avoid Balena-specific APIs
- **Risk**: Security of web dashboard (if implemented)
  - **Mitigation**: Disabled by default, local network only, optional feature

---

## Alternatives Considered

### Alternative 1: Single Unified Admin UI
Combine maintainer/devops tools into the SQLAdmin dashboard.

**Why Rejected**:
- Clutters end-user interface with technical noise
- Burn-in tests can take 60+ minutes (not suitable for web UI timeout)
- Hardware diagnostics require system-level access (awkward via web)

### Alternative 2: Bash Scripts Only
Provide shell scripts instead of `just` recipes.

**Why Rejected**:
- `just` provides better discoverability (`just --list`)
- `just` handles dependencies and command composition elegantly
- Already using `justfile` for dev workflows

### Alternative 3: Balena Supervisor API
Use Balena's built-in device management API for operations.

**Why Rejected**:
- Limited to Balena environments (not portable to Tier 2/3)
- Requires learning Balena-specific APIs
- Less flexible than custom scripts

---

## Implementation Plan

### M8.5.1: CLI Tooling
1. Extend `justfile` with maintainer recipes
2. Document commands in `docs/60_ops/runbooks.md`
3. Add commands to deployment checklist
4. Test on Tier 1 Balena device

### M8.5.2: Web Dashboard (Optional/Future)
1. Prototype minimal Flask app
2. Implement burn-in progress visualization
3. Add log tailing web interface
4. Security review (ensure local-only access)

---

## References

- [Deployment Checklist](../../60_ops/deployment_checklist.md) - Lists validation tasks
- [ROADMAP.md](../../../ROADMAP.md) - M8.5 milestone definition
- [Runbooks](../../60_ops/runbooks.md) - Operational procedures
- [ADR-0002](0002-decoupled-ui.md) - Decoupled UI architecture (end-user admin)

---

## Appendix: Command Categories

### Validation Commands (Pre-Deployment)
- `just burn-in-test` - Hardware thermal stability
- `just validate-network` - Network resilience (offline buffering)
- `just validate-gold-corpus` - STT accuracy (WER < 5%)
- `just validate-security` - TPM/encryption verification

### Diagnostic Commands (Troubleshooting)
- `just health-check` - All services + hardware status
- `just gpu-info` - CUDA/cuDNN availability
- `just disk-usage` - Storage utilization report
- `just temp-monitor` - Real-time temperature logging

### Operational Commands (Maintenance)
- `just logs-aggregate` - Combined service logs
- `just backup-config` - Export settings/phraseSets
- `just restore-config` - Import settings
- `just reset-buffers` - Clear recovery buffers (troubleshooting)
