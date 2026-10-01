# ADR-0006 — Browser authentication with server-side sessions

- **Status:** Accepted (product owner, 2026-09-30, change 0002)
- **Date:** 2026-09-30
- **Deciders:** product owner
- **Change record:** docs/changes/0002-phase-1-discovery.md

## Context
Auth tokens must not be in `localStorage`. The web client is served from the same site as the API (proposed). Permission and membership revocation must take effect immediately. The legacy system used SimpleJWT access/refresh tokens in HttpOnly cookies with a custom CSRF check and refresh blacklist.

## Options considered
1. **JWT in HttpOnly cookies** (legacy) — stateless verification, but revocation needs a blacklist, refresh rotation logic, and custom CSRF handling; tokens tend to cache claims.
2. **Server-side sessions in HttpOnly cookies** — session ID only in the cookie; revocation = delete session; framework CSRF built in; session store in PostgreSQL (or Redis).
3. **Bearer tokens in memory + refresh cookie** — more moving parts; needed only for third-party/native clients.

## Decision
Accepted with the amendments listed below; where they differ from this paragraph, the amendments win (notably the cookie prefix, and the "active membership" in the session, which is now only a default).

Option 2 for the web client: `HttpOnly`, `Secure`, `SameSite=Lax` (or `Strict` if flows allow), host-only cookie; CSRF token on unsafe methods; session rotated on login and privilege change; all sessions of a user invalidated on password change/reset; idle and absolute timeouts (values in Phase 2); the session stores the active membership ID. Token-based auth for native apps or integrations is deferred until needed (separate ADR).

## Consequences
- Positive: simplest correct option; instant revocation; no token handling in JS.
- Negative: session store lookups per request (cheap); cross-site API use not supported without a new ADR.

## Amendments at acceptance
Adopted by the product owner on 2026-09-30 from security findings C6-1..C6-8 (change 0002, Track C), together with the answers to Q7 and Q8. Detail: `docs/architecture/authorization.md` ("Authentication and sessions") and `docs/conventions/api.md`.

- **C6-1 Single host, restaurant in the path.** Tenants get no subdomains. The restaurant identifier is in the URL path. The session cookie is `__Host-` prefixed (`Secure`, `Path=/`, no `Domain`, `HttpOnly`). User uploads are served from a different registrable domain or through short-lived signed object-storage URLs.
- **C6-2 Per-request tenant.** The tenant is resolved on every request from the URL path and validated against the user's active memberships. The session holds only a default (last-used) restaurant, which is used for landing redirects. A request whose credential is bound to a different tenant than the path gets 409 and writes nothing.
- **C6-3 Login CSRF.** CSRF is enforced on every unsafe method, authenticated or anonymous (login, signup, reset, invite accept). `CSRF_TRUSTED_ORIGINS` is strict. No GET has side effects.
- **C6-4 Session store.** A custom session model/backend with `user_id`, `created_at` and `last_seen_at` supports idle and absolute timeouts and "log out everywhere". The session key is stored hashed. Serialization is JSON only.
- **C6-5 Store.** Sessions live in PostgreSQL, in a platform-level table without RLS that only the identity module accesses. There is no Redis session store.
- **C6-6 Realtime.** Same-origin SSE is preferred. Any WebSocket handshake checks `Origin` against an allow-list. Streams have a bounded lifetime.
- **C6-7 Device sessions and operators.** Q7 = yes. Shared kitchen/counter devices use a separate credential type, the device session. It is bound to one restaurant, carries a fixed limited permission set, can be revoked per device and has no idle logout. Which permission may sign a device in or out is still open (UX-5, blocking Phase 2). The operator console uses its own host and cookie name, mandatory MFA and a short absolute timeout.
- **C6-8 Rotation.** The session ID rotates on login, restaurant switch and password or MFA change. Changes to *other* users rely on per-request evaluation (ADR-0005).
- **MFA (Q8).** Optional TOTP is available to owners. MFA is mandatory for platform operators.

## Revisit when
Native apps (Q23) or third-party API clients are required.
