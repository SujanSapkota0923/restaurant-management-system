# API Conventions

**Status:** Proposed. Applies to all HTTP endpoints. The tenant-in-path shape follows the accepted ADR-0006 (C6-1/C6-2). The concrete URL layout below is a proposal (REVIEW). Procedure: `api-design` skill.

## Basics
- JSON over HTTPS. Prefix `/api/v1/`. One host, the same origin as the web client (ADR-0006 C6-1). No per-tenant subdomains.
- Resource paths are plural nouns. IDs are UUIDs.
- Business transitions are commands: `POST /api/v1/r/{tenant_id}/orders/{id}/cancel`. `status` is read-only on resources.
- Field names `snake_case`. Timestamps ISO 8601 UTC. Money as decimal strings (`"12.50"`) with a currency code on the parent resource.

## URL layout and tenant context (REVIEW)
Paths belong to one of three planes (`docs/architecture/tenancy.md`, "Planes"):

| Plane | Path shape | Tenant context | Examples |
|-------|------------|----------------|----------|
| Identity | `/api/v1/auth/…`, `/api/v1/me/…`, `/api/v1/invites/…` | None. User-scoped reads only | `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/logout-all`, `GET /api/v1/me`, `GET /api/v1/me/memberships` (restaurant ID, name, status, own membership status), `POST /api/v1/invites/lookup` (token in the body, never the query string), `POST /api/v1/invites/accept` |
| Tenant | `/api/v1/r/{tenant_id}/…` | The `{tenant_id}` path segment, validated per request | `GET /api/v1/r/{tenant_id}/menu-items/{id}`, `POST /api/v1/r/{tenant_id}/orders/{id}/cancel`, `GET /api/v1/r/{tenant_id}/events` (SSE) |
| Platform | Operator host only | None (break-glass separate, Q5) | Not served on the tenant host |

- The web client mirrors this with `/r/{tenant_id}/…` routes. Each tab's URL therefore fixes its restaurant.
- `{tenant_id}` is the tenant UUID. It is stable, needs no rename handling, and creates no slug-collision or slug-squatting problem. A human-readable slug is a possible later addition (REVIEW).
- The tenant is resolved **only** from the path segment and validated against the session user's active memberships on every request. It is never read from a body, query string or header.
- An unparseable ID, or a restaurant without an active membership, returns 404 `not_found`. The response does not say whether the restaurant exists.
- A credential bound to one restaurant (a device session) calling another restaurant's path returns 409 `tenant_mismatch`, and nothing is written. The check runs before any lookup.
- The session stores only a default restaurant. `GET /api/v1/me` returns it so the client can redirect after login.
- `POST /api/v1/me/default-restaurant` sets the default restaurant (restaurant switch) and rotates the session ID (C6-8).
- **CSRF** is required on every unsafe method, including anonymous identity-plane POSTs (login, signup, reset, invite lookup/accept). Failure returns 403 `csrf_failed`.
- **Cookies:** the session cookie uses the `__Host-` prefix. The CSRF cookie uses the `__Host-` prefix too; it is readable by JS but holds no session.
- **Realtime:** use SSE on the same origin. The channel is derived server-side from the path tenant. Any WebSocket endpoint checks `Origin` against an allow-list. Streams have a bounded lifetime.
- **Uploads** are never served from this host. They come from a separate registrable domain or through short-lived signed URLs.

## Status codes
| Code | Use |
|------|-----|
| 200 / 201 / 204 | Success / created / no content |
| 400 | Validation error |
| 401 | Not authenticated |
| 403 | Authenticated member lacks permission (same tenant); `csrf_failed` |
| 404 | Not found, **or belongs to another tenant**, or no active membership in the path restaurant |
| 409 | Invalid state transition, version conflict, idempotency-key reuse with different payload, `tenant_mismatch` (tenant-bound credential vs path) |
| 429 | Rate limited |
| 5xx | Server error — generic message only |

## Error envelope
```json
{
  "error": {
    "code": "order_not_cancellable",
    "message": "This order has already been paid and cannot be cancelled.",
    "fields": { "reason": ["This field is required."] },
    "request_id": "b0c1…"
  }
}
```
`code` is stable and machine-readable; `message` is safe for users; `fields` only for validation. Never stack traces, SQL, or internal details.

## Lists
Cursor or limit/offset pagination (fixed in Phase 2), default 50, max 200. Filters and ordering are explicit and documented; unknown filter params → 400.

## Concurrency and retries
- `Idempotency-Key` header on creates of orders, payments and other retry-prone commands, scoped to (tenant, principal, key); same key + same payload → same response; same key + different payload → 409.
- Editable resources expose `version`; updates send it; mismatch → 409.

## Versioning and compatibility
Additive changes are allowed within `v1`. Removing/renaming fields, changing meaning or status codes is breaking → `APPROVAL` and a deprecation plan.

## Documentation
Every endpoint is described in the generated OpenAPI schema (tooling fixed in Phase 2) with its permission code.
