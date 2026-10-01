# Tenancy and Isolation

**Status:** Accepted (ADR-0003 with amendments C3-1..C3-10; tenant resolution per ADR-0006 C6-1/C6-2; product owner, 2026-09-30, change 0002). Nothing is built yet. Implementation and proof come in the Phase 2 spike. Role names and SQL below are illustrative; `data-engineer` fixes the exact names. Owner: `architect` + `security-engineer`.

## Model
- **Platform-level tables** (no `tenant_id`): users/identity, sessions (ADR-0006 C6-4/C6-5), the tenants registry, platform operators, the global permission catalog, and system role templates.
- **Tenant-owned tables:** everything operational (memberships, invitations, roles, device registrations, menu, tables, orders, payments, inventory, reservations, settings, audit events). Each has a non-null, immutable `tenant_id`.

## Planes
Every database transaction belongs to exactly one plane:

| Plane | Context set | Sees | Used by |
|-------|-------------|------|---------|
| Tenant | `app.tenant_id` | One tenant's rows | All `/api/v1/r/<tenant>/…` requests, per-tenant jobs |
| Identity | `app.user_id` only (no tenant) | The session user's own memberships plus the name and status of those restaurants (C3-1a); invite lookup through the definer function (C3-1c) | Login, `me`, restaurant switcher, invite acceptance |
| Platform | none | Platform tables only; tenant tables return 0 rows | Session and auth lookup, the scheduler, and the operator console (break-glass is designed separately, Q5) |

## Defense in depth: three layers

1. **Request layer (tenant resolution).**
   - The tenant comes from the URL path (`/api/v1/r/<tenant_id>/…`, see `docs/conventions/api.md`). It is resolved and validated on **every request**. The session holds only a default restaurant, used for landing redirects (ADR-0006 C6-2).
   - Validation happens inside the tenant transaction, before any handler code runs. If the session user has no active membership in the path tenant, or the tenant is not active, the transaction rolls back and the response is 404. A credential bound to one tenant (a device session) used with a different path tenant returns 409 `tenant_mismatch`. That check runs before any lookup, so it reveals nothing about whether the other tenant exists.
   - The tenant is never read from request bodies, query strings or headers.
2. **Application layer (scoped data access).**
   - There is exactly one tenant-transaction entry point (middleware or handler decorator; C3-4). It opens the transaction, sets the context and validates the membership.
   - Tenant-owned models are accessed only through the tenant-scoped repository. The repository asserts that the entry point is active and raises otherwise.
   - Code outside the transaction (auth/session middleware, throttling, post-response hooks) touches platform tables only. `on_commit` callbacks only enqueue work. Streaming responses run one short transaction per poll and never hold a transaction open.
   - Unscoped access to tenant data exists only in migrations (below) and in the future audited platform path (Q5).
3. **Database layer (PostgreSQL Row-Level Security).**
   - Every tenant-owned table has `ENABLE` and `FORCE ROW LEVEL SECURITY` and a tenant policy, with the same expression in `USING` and `WITH CHECK`:
     `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid` (C3-3). A reused connection returns `''`, which `NULLIF` turns into NULL, so the result is 0 rows rather than an error.
   - Context is set only with `SELECT set_config('app.tenant_id', %s, true)`, with a UUID that has already been parsed and validated, passed as a bound parameter (C3-2). `app.user_id` is set the same way. Session-level `SET` and string-built `SET LOCAL` are forbidden.
   - **Identity-scoped membership policy (C3-1a).** Memberships carry a second, SELECT-only policy:
     `NULLIF(current_setting('app.tenant_id', true), '') IS NULL AND user_id = NULLIF(current_setting('app.user_id', true), '')::uuid`.
     It applies only in identity-plane transactions. It never widens a tenant-plane query. It never allows writes.
   - **Restaurant name and status (C3-1a).** The app role reads only `id`, `name` and `status` of the tenants registry (column grants). Rows are limited, by RLS or a `security_invoker` view, to the current tenant or to tenants in which the `app.user_id` user has a membership.
   - **Invite lookup (C3-1c).** A single reviewed `SECURITY DEFINER` function takes a token hash and returns at most one invitation: its ID, tenant ID, restaurant name, invited email, status and expiry. It has a pinned `search_path` and is owned by a dedicated `NOLOGIN` role. That role has only the needed column grants and `BYPASSRLS`, the written reason being that `FORCE` RLS also applies to the definer. Accepting the invite is a separate write in a tenant-plane transaction for the invite's tenant, after the invited email is matched against the user's verified email (TM-07).
   - **Tenant key rules (C3-9).** The app role cannot UPDATE `tenant_id`. Every unique constraint on a tenant table leads with `tenant_id`. Parents carry `UNIQUE (tenant_id, id)` so that children can use composite FKs.

## Database roles and credentials (C3-5, C3-6, C3-10)

| Role (illustrative) | Login | Used by | Properties |
|---------------------|-------|---------|------------|
| `rms_migrator` | yes | Migration job only | Owns schema objects. Subject to `FORCE` RLS. `BYPASSRLS` only with a written reason in the change record |
| `rms_app` | yes | API and worker | Not owner, not superuser, no `BYPASSRLS`, not a member of `rms_migrator` or any owner role. DML only, via `ALTER DEFAULT PRIVILEGES`. No UPDATE on `tenant_id`, only INSERT/SELECT on audit tables (TM-18). `statement_timeout` and `idle_in_transaction_session_timeout` set |
| `rms_scheduler` | yes | Periodic scheduler only (C3-8) | SELECT on the `id` and `status` columns of the tenants registry. Can enqueue jobs. No tenant tables |
| invite-lookup owner | no | Owns the C3-1c function | See above |

- Migrations run as a **separate job** with a separate DB alias and credentials. Those credentials are absent from the API, worker and scheduler environments, and a CI check of the runtime environment enforces this (R16, TM-29).
- Data migrations iterate tenants from the registry and set tenant context for each tenant.
- Pooling: transaction pooling is compatible with `set_config(..., true)`. Django persistent connections are allowed only because of the C3-2 reuse test.

`rms_scheduler` is a separate credential, not a new service or datastore. It exists so that `rms_app` cannot list all tenants (REVIEW: data-engineer + security-engineer).

## Referential integrity across tenants
Tenant-owned rows that reference other tenant-owned rows use composite foreign keys `(tenant_id, x_id) → (tenant_id, id)`. A row therefore cannot point into another tenant, even through a bug. The exact mechanism with the Django ORM is confirmed in the Phase 2 spike.

## Side channels
- Cache keys, object-storage paths (`tenants/<tenant_id>/…`), realtime channels, job payloads and log context all include `tenant_id`.
- Realtime channel names are derived from the resolved tenant, never from connection state or client input (TM-20).
- **Jobs:** the payload carries IDs and `tenant_id` only. Each job runs in one transaction that sets tenant context before any query, and re-reads its data under RLS (TM-24).
- **Cross-tenant periodic work:** the scheduler reads the registry and enqueues one job per tenant (C3-8).

## Platform access (break-glass)
Platform operators do not use tenant endpoints. They use a separate host and cookie with mandatory MFA (ADR-0006 C6-7, Q8). Any cross-tenant capability (support tooling, platform reports) is a separate module and role, fully audited, and designed under `APPROVAL` (Q5).

## Required checks and tests (Phase 2 harness, then every change)
- **CI catalog check (C3-5, R1).** It asserts that:
  - every tenant table has RLS enabled and forced, plus a policy;
  - the app role is not owner, not superuser, has no `BYPASSRLS`, and is a member of no owner or migration role;
  - every view has `security_invoker = true`;
  - every `SECURITY DEFINER` function is on the reviewed allow-list (in v1, only the C3-1c function);
  - no materialized view covers tenant data;
  - the only `BYPASSRLS` roles are the allow-listed ones.
- **Tests run as the app role (C3-7).** A guard test fails if `current_user` is a superuser or has `BYPASSRLS`.
- Two-tenant fixtures by default.
- Per endpoint: B's IDs from A's session return 404 with no side effects. A path tenant without membership returns 404. A device bound to A calling B's path returns 409.
- RLS: without tenant context, queries return 0 rows and writes fail. A connection reused after a tenant request carries no context (C3-2).
- Identity plane: a user sees only their own memberships and those restaurants' name and status. The user-scoped policy adds nothing inside a tenant transaction. Invite lookup returns at most the one matching invite.
- Composite FK: inserting a cross-tenant reference fails at the DB. The same natural key in A and B succeeds in both (TM-17).
- Jobs: a job for A never reads or writes B. A job without context reads 0 rows.

## Alternatives considered
See ADR-0003: schema-per-tenant (legacy `../rms`, via django-tenants) and database-per-tenant.
