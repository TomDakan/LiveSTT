# ADR-0016: Admin Authentication

**Date**: 2026-04-01
**Status**: ACCEPTED

---

## Context

Milestone 6.5 adds an admin interface for session management, schedule configuration, transcript export, and system status. Several routes that were previously protected by a static `ADMIN_TOKEN` header (ADR-0015 §2) need a proper authentication mechanism.

Requirements:
1. **Single admin role** — Live STT is an appliance with one operator, not a multi-user system. There is no need for user accounts, roles, or OAuth/OIDC.
2. **Low complexity** — The authentication layer must be simple to configure and maintain on edge hardware (NUC N97).
3. **No external dependencies** — No database, no identity provider, no network call during auth. The appliance may operate on isolated LANs.
4. **Dev-mode bypass** — In development, authentication should be optional so developers can test without configuring credentials.

The previous `ADMIN_TOKEN` approach (a static plaintext token in an env var) was adequate for early milestones but has drawbacks: the token never expires, is easily leaked in logs or browser history, and offers no password-based login flow for the admin UI.

---

## Decision

### 1. Password Verification — bcrypt

A single admin password is configured via the `ADMIN_PASSWORD_HASH` environment variable, which stores a bcrypt hash (e.g., generated with `python -c "import bcrypt; print(bcrypt.hashpw(b'password', bcrypt.gensalt()).decode())"`).

- On `POST /admin/auth`, the submitted plaintext password is verified against the hash using `bcrypt.checkpw()`.
- **Dev-mode fallback**: If `ADMIN_PASSWORD_HASH` is unset or empty, any password is accepted and a warning is logged. This allows local development without configuring credentials.

### 2. Token Issuance — Ephemeral JWT

On successful password verification, the server issues a short-lived JWT (HS256):
- **Secret**: Generated at startup via `secrets.token_hex(32)` and stored in `app.state.jwt_secret`. The secret is never persisted to disk.
- **TTL**: Configurable via `ADMIN_TOKEN_TTL_S` (default: 3600 seconds / 1 hour).
- **Payload**: Only standard claims (`exp`, `iat`) — no user identity, roles, or custom claims.

### 3. Route Protection — FastAPI Dependency

A `require_admin` FastAPI dependency extracts the `Authorization: Bearer <token>` header, decodes the JWT, and raises `401 Unauthorized` on missing or invalid tokens.

Protected routes (all mutating admin operations):
- `POST /session/stop`
- `POST /session/start` — remains **unauthenticated** per ADR-0015 §2
- `DELETE /admin/sessions/{session_id}`
- `POST /admin/schedules`, `PUT /admin/schedules/{schedule_id}`, `DELETE /admin/schedules/{schedule_id}`
- `POST /admin/backup`

Unprotected routes (read-only):
- `GET /admin/status` — system status (heartbeats, stream stats, disk)
- `GET /health` — healthcheck
- `GET /session/status` — current session state
- All viewer/display endpoints and WebSocket connections

### 4. Ephemeral Secret — Sessions Do Not Survive Restarts

Because `jwt_secret` is generated at startup and not persisted, all issued JWTs are invalidated when the api-gateway process restarts. This is an intentional tradeoff:
- **Acceptable** because Live STT is an appliance where restarts are infrequent and re-login is trivial (single password, no 2FA).
- **Benefit**: No secret management, no risk of leaked persistent keys on the filesystem.

---

## Consequences

### Positive
- Zero external dependencies for auth — no database, no Redis, no identity provider.
- Simple operator experience: set one env var (`ADMIN_PASSWORD_HASH`), done.
- Dev-mode fallback eliminates auth friction during development.
- Short-lived JWTs limit the window of exposure if a token is leaked.
- `require_admin` as a FastAPI dependency makes it easy to gate new routes consistently.

### Negative
- **Single-password model** does not support per-user audit trails. Acceptable for the current single-operator use case.
- **Ephemeral JWT secret** means all admin sessions break on restart. Mitigation: restarts are rare on an appliance; re-login takes seconds.
- **No refresh token flow** — when the JWT expires, the admin must re-enter the password. Mitigated by the configurable TTL (default 1 hour).
- **bcrypt CPU cost** on Tier 1 hardware (N97) is measurable (~200-400ms per verify). Acceptable since login is a rare, interactive operation.

### Security Considerations
- The bcrypt hash is stored in an env var, not in code or config files committed to git.
- The dev-mode bypass (`ADMIN_PASSWORD_HASH` unset) logs a warning on every auth attempt. The deployment checklist must verify this is set in production.
- `POST /session/start` remains unauthenticated per ADR-0015. This is intentional: any attendee should be able to start transcription.

### Future Work
- If multi-user support is ever needed, migrate to NATS KV-backed user records with scoped JWTs. The `require_admin` dependency interface would remain unchanged.
- Consider persisting `jwt_secret` in NATS KV or a file to survive restarts, if restart frequency increases.

---

## References

- [ADR-0015 — Session Lifecycle](0015-session-lifecycle.md) (§2: session authorization)
- [ROADMAP.md — Milestone 6.5](../../ROADMAP.md)
- [Threat Model](../threat_model.md)
