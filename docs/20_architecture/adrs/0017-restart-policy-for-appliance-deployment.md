# ADR-0017: Restart Policy for Appliance Deployment

**Date**: 2026-04-02
**Status**: ACCEPTED

---

## Context

Live STT is an always-on appliance deployed on an ASRock NUC N97. Power loss
is a normal operating condition (circuit breakers, storms, accidental unplugs).
The system must recover fully without human intervention after power is
restored.

Docker Compose offers three relevant restart policies:

| Policy | After crash | After `docker stop` | After daemon restart (power loss) |
|---|---|---|---|
| `on-failure` | Yes | No | No |
| `unless-stopped` | Yes | No | No |
| `always` | Yes | Yes | Yes |

The current policy (`unless-stopped`) does not restart services after a Docker
daemon restart, which is the exact scenario that follows power loss on the NUC.

## Decision

Use `restart: always` as the default policy for all services in
`docker-compose.yml`.

When service orchestration is added (M7.5 Batch 5), intentionally disabled
services will be managed via `docker update --restart=no` (bare Docker) or
the Balena Supervisor API (BalenaOS). This is the standard mechanism for
overriding restart policy at runtime.

## Consequences

- **Positive**: Full auto-recovery after power loss with no operator action
- **Positive**: Consistent behavior across bare Docker and BalenaOS deployments
- **Negative**: `docker stop <service>` is no longer sufficient to permanently
  disable a service — it will restart on next daemon restart. This is acceptable
  because service disable is not yet a supported operation; it will be handled
  explicitly in M7.5 Batch 5.
