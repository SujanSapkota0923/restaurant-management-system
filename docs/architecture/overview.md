# Architecture Overview

**Status:** Proposed as a whole. The decisions marked Accepted in the table below are binding. Nothing is built yet. Binding decisions live in `docs/decisions/`; this page summarises them and must be kept in sync.

## Shape

A **modular monolith**: one deployable backend with strict internal module boundaries (one module per bounded context), one PostgreSQL database, a background-job worker, and a mobile-first web client (installable PWA, ADR-0004). Rationale: a single team, strong transactional needs (orders, payments, stock), and tenant isolation are easiest to get right in one process with one database. Modules are kept separable so a context can be extracted later if evidence demands it.

```
 Browser / PWA  ──HTTPS──▶  API (modular monolith)  ──▶  PostgreSQL (RLS)
  (mobile-first)            │  ├─ identity                ▲
                            │  ├─ tenancy                 │
                            │  ├─ access (authz)          │
                            │  ├─ catalog (menu)          │
                            │  ├─ floor (tables)          │
                            │  ├─ ordering / kitchen      │
                            │  ├─ billing                 │
                            │  ├─ inventory               │
                            │  ├─ reservations            │
                            │  ├─ reporting (read side)   │
                            │  └─ audit                   │
                            └──▶ job queue ──▶ worker ────┘
                                   ▲
                      scheduler ───┘ (enqueues one job per tenant)
 migration job ──(separate credentials, never in API/worker env)──▶ PostgreSQL
```

The web client and API share one host. The restaurant is in the URL path (`/r/<tenant_id>/…`, API `/api/v1/r/<tenant_id>/…`). The operator console runs on its own host.

Contexts and their ownership: `domain-model.md`.

## Cross-cutting decisions (summaries)

| Concern | Decision | Status | Source |
|---------|----------|--------|--------|
| Rebuild vs refactor legacy | Rebuild; legacy is reference only | Accepted by brief | ADR-0002 |
| Tenancy | Shared schema, `tenant_id` on every tenant-owned row, PostgreSQL RLS (`NULLIF` policy, `set_config` with a bound UUID, non-owner app role, separate migration job) + app-level scoping; one identity-scoped membership policy and one invite definer function; CI catalog checks; tests as the app role | Accepted 2026-09-30 (with amendments) | ADR-0003, `tenancy.md` |
| Stack | Python/Django + DRF, PostgreSQL, React + TypeScript + Vite (PWA) | Accepted | ADR-0004 |
| Identity / membership / authz | User ↔ Membership ↔ Roles & permissions, permission-code checks, per-request evaluation; permission catalog v1 and role templates approved (C6.19), device-eligibility list Proposed | Accepted 2026-09-30 | ADR-0005, `authorization.md` |
| Sessions | Server-side sessions (PostgreSQL store, hashed keys) in a `__Host-` HttpOnly cookie on a single host; tenant in the URL path, validated per request; CSRF on all unsafe methods; device sessions for shared tablets; MFA optional for owners, mandatory for operators | Accepted 2026-09-30 (with amendments) | ADR-0006, `authorization.md` |
| Retention | Orders, payments and audit kept 7 years; staff personal data minimized after membership removal (details open) | Answered (Q20); mechanism in Phase 2 | `requirements.md` Q20, `authorization.md` |
| Audit | Explicit business audit events, same transaction, append-only | Proposed | `audit-logging.md` |
| Realtime (kitchen/orders) | Transactional outbox → push channel (SSE/WebSocket) scoped per tenant | Planned (decide in Phase 5) | — |

## Layering inside each module

`api` (handlers: auth, parse, respond) → `services` (use cases: rules, transactions, audit) → `domain` (entities, invariants, state machines) → `data` (tenant-scoped repositories/models). Modules talk to each other only through the other module's service interface or domain events.

## Non-functional targets (proposed; confirm in Phase 1)
- Order-taking API p95 < 300 ms at expected peak.
- New kitchen ticket visible < 3 s after order is sent.
- Zero cross-tenant data exposure (tested on every endpoint).
- RPO ≤ 15 min, RTO ≤ 4 h for production (Phase 10).
