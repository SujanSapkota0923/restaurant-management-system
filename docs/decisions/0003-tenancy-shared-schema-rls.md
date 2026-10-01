# ADR-0003 — Tenancy: shared schema with tenant key and PostgreSQL RLS

- **Status:** Accepted (product owner, 2026-09-30, change 0002)
- **Date:** 2026-09-30
- **Deciders:** product owner; proposed by bootstrap session (architect + security-engineer roles)
- **Change record:** docs/changes/0002-phase-1-discovery.md

## Context
Tenant isolation is the top architectural requirement. Isolation must hold even when IDs are manipulated, the UI is bypassed, or a permission is misconfigured — so it needs a database-level backstop, not only application filters. The architecture must allow one user to belong to several restaurants. The legacy system uses schema-per-tenant (django-tenants).

## Options considered
1. **Schema per tenant** (legacy) — strong separation via `search_path`. Cons: migrations run N times (slow, partial-failure states), connection/`search_path` leakage bugs are silent, cross-tenant identity/membership lives awkwardly in the public schema (legacy even duplicated the user app in both), platform-wide reporting is hard, thousands of schemas strain PostgreSQL catalog.
2. **Database per tenant** — strongest isolation. Cons: heavy operations, cost, connection management; overkill for small restaurants.
3. **Shared schema + `tenant_id` + RLS + scoped app layer** — one migration path, simple membership across tenants, DB-enforced isolation via policies, easy platform aggregates through a dedicated audited path. Cons: RLS must be set up precisely (non-owner role, `FORCE`, per-transaction setting); a noisy tenant shares resources.

## Decision
Accepted with the amendments listed below; where they differ from this paragraph or the Consequences, the amendments win.

Option 3, as specified in `docs/architecture/tenancy.md`: three layers (server-side tenant resolution from active membership, tenant-scoped data access, PostgreSQL RLS with a non-owner, non-`BYPASSRLS` application role), composite tenant foreign keys, tenant-carrying side channels, and a mandatory two-tenant isolation test suite.

## Consequences
- Positive: isolation enforced twice; simple migrations; supports multi-restaurant users.
- Negative: every request must run in a transaction that sets `app.tenant_id`; pooling must respect that; RLS policy mistakes are critical — covered by RLS tests in CI.
- Follow-ups: Phase 2 spike proving RLS with the chosen ORM and pooler; decide whether very large tenants could later be moved to a dedicated database.

## Amendments at acceptance
Adopted by the product owner on 2026-09-30 from security findings C3-1..C3-10 (change 0002, Track C). Detail: `docs/architecture/tenancy.md`.

- **C3-1 Identity-scoped reads (options a + c).** (a) A second, SELECT-only RLS policy on memberships matches `user_id` against `app.user_id` and applies only when no tenant context is set. Through it, a signed-in user sees their own memberships and, for those restaurants only, the restaurant name and status. (c) An invite is looked up by token hash through one reviewed `SECURITY DEFINER` function. No other identity-scoped path exists.
- **C3-2 Setting context.** Context is set only with `set_config('app.tenant_id', $1, true)` (and `app.user_id` the same way), with a validated UUID bound as a parameter. Session-level setting is forbidden. A test proves that a reused connection starts with no context.
- **C3-3 Policy expression.** Policies use `NULLIF(current_setting('app.tenant_id', true), '')::uuid`.
- **C3-4 One entry point.** A single tenant-transaction entry point opens the transaction and sets the context. The scoped repository asserts that it is active. `on_commit` callbacks only enqueue work. Streaming uses one short transaction per poll.
- **C3-5 CI catalog check.** CI asserts that the app role is not owner, not superuser and has no `BYPASSRLS`; that it is not a member of the owner or migration role; that every tenant table has RLS enabled and forced plus a policy; that every view uses `security_invoker`; that every `SECURITY DEFINER` function is on a reviewed allow-list; and that no materialized view exposes tenant data.
- **C3-6 Migrations.** Migrations run as a separate job, with a separate DB alias and credentials that are absent from the API and worker environments. Data migrations iterate tenants from the registry and set context per tenant. `BYPASSRLS` requires a written reason. `ALTER DEFAULT PRIVILEGES` grants the app role DML only.
- **C3-7 Tests.** Tests connect as the app role. A guard test asserts that `current_user` is not a superuser and has no `BYPASSRLS`.
- **C3-8 Cross-tenant jobs.** A scheduler reads the tenants registry (platform plane) and enqueues one job per tenant. The worker sets tenant context per job.
- **C3-9 Keys.** The app role cannot UPDATE `tenant_id`. Every unique constraint on a tenant table leads with `tenant_id`. Parents referenced by composite FKs carry `UNIQUE (tenant_id, id)`.
- **C3-10 Timeouts.** The app role has `statement_timeout` and `idle_in_transaction_session_timeout` set. Transaction pooling is allowed; the C3-2 test covers persistent connections.
- **Tenant resolution** changes with ADR-0006 C6-1/C6-2. The tenant comes from the URL path and is validated against the user's memberships on every request. It is no longer the session's "active membership".

## Revisit when
A tenant requires contractual physical isolation, or scale shows noisy-neighbour problems that indexing/partitioning cannot fix.
