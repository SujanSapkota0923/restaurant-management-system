# Tenancy and Isolation

**Status:** Accepted (ADR-0003 with amendments C3-1..C3-10; tenant resolution per ADR-0006 C6-1/C6-2; product owner, 2026-09-30, change 0002). The tenant-plane foundation is **Built** in change 0004 (see "As built" below; items are marked **Built (0004)** or **Planned**). Role names are the local/CI defaults; deployed names come from the environment (`DB_APP_USER`, Phase 10). Owner: `architect` + `security-engineer`.

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

## As built (change 0004)
| Piece | Where | What it does |
|-------|-------|--------------|
| Tenants registry | `rms.tenancy.data.models.Restaurant`, table `tenancy_restaurant` | `id` uuid (v4), `name` (max 200, not blank; OQ1), `status` (`active`/`suspended`/`closed`, DB `CHECK`), `created_at`, `updated_at`. Platform table owned by the migrator. RLS **enabled, not forced** (D4) with one `FOR SELECT` policy `restaurant_tenant_read` (`id` = current tenant). The app role has `SELECT (id, name, status)` and nothing else. No status-change command yet (operator console) |
| Tenant entry point | `rms.tenancy.data.context.tenant_transaction(tenant_id)` | The only runtime code that sets `app.tenant_id`. Takes exactly a `uuid.UUID`. Opens a `durable` (outermost) transaction on `default`. Its first statement reads both planes' previous values and sets the tenant with a bound parameter; a non-empty previous value raises `TenantContextActive` (leak detection). Clears the setting before a normal exit and resets its contextvars inside the transaction, so `on_commit` callbacks and later code run without context. `current_tenant_id()` raises `TenantContextMissing` outside it |
| Identity entry point | `identity_transaction(user_id)` | Same rules for `app.user_id`. The two planes never mix (each raises if the other is set). Its policies arrive in 0005 |
| Scoped data access | `TenantOwnedModel`, `TenantManager`, `TenantQuerySet` (`rms.tenancy.data.models`) | The tenant-scoped repository of layer 2. Rules: `docs/conventions/backend.md` "Tenant-owned models" |
| Migration operations | `rms.tenancy.data.rls` | `enable_tenant_rls`, `restrict_tenant_key_update`, `grant_update_columns`, `composite_tenant_fk`, `for_each_tenant`; the registry and `django_migrations` lock-downs. Role names come from `DB_APP_USER` and are checked against `pg_roles` (C-11) |
| Tenant resolution | `rms.tenancy.api.views.TenantAPIView` | Base view for `/api/v1/r/<uuid:tenant_id>/…`. Layer 1 below |
| Isolation harness | `rms.tenancy.tests` (`harness.py`, `factories.py`, the test-only `probe` app) | `docs/conventions/backend.md` "Tests" |
| Catalog check | `rms/tenancy/tests/catalog.py` | Below, "Required checks" |

## Defense in depth: three layers

1. **Request layer (tenant resolution).**
   - The tenant comes from the URL path (`/api/v1/r/<tenant_id>/…`, see `docs/conventions/api.md`). It is resolved and validated on **every request**. The session holds only a default restaurant, used for landing redirects (ADR-0006 C6-2).
   - **Built (0004):** `TenantAPIView.dispatch` runs the whole request inside `tenant_transaction` for `self.kwargs["tenant_id"]` (routed only as `<uuid:tenant_id>`, so a malformed or upper-case value never reaches a view and gets the `handler404` envelope). `initial()` then runs authentication, `resolve_active_tenant` (one registry query: unknown and non-active give the same result), `check_principal`, permissions and throttles, in that order. Every failure is the same `404 not_found` before any tenant-table access, with the same body, headers and query count (R29 accepts the remaining timing difference). A response with status ≥ 400 rolls the transaction back; a success response for a transaction marked for rollback, and any streaming response, becomes a 500. `dispatch`, `initial`, `resolve_active_tenant` and `check_principal` are `@final`.
   - **Closed until 0005/0006:** `check_principal` always raises 404, so no request can pass it yet. 0005/0006 add the membership and device-session check in `rms.access.api` (the only reviewed override). No tenant route is mounted in `config/urls.py` in 0004, and tests fail on a tenant route there, an override outside test packages, a non-`uuid` tenant converter or an `AllowAny` tenant view.
   - Validation happens inside the tenant transaction, before any handler code runs. If the session user has no active membership in the path tenant, or the tenant is not active, the transaction rolls back and the response is 404. A credential bound to one tenant (a device session) used with a different path tenant returns 409 `tenant_mismatch`. That check runs before any lookup, so it reveals nothing about whether the other tenant exists. (Tenant status: **Built (0004)**. Membership: **Planned (0005)**; it must issue the same queries whether the tenant is active or not. Device 409: **Planned (0006)**.)
   - The tenant is never read from request bodies, query strings or headers.
2. **Application layer (scoped data access).**
   - There is exactly one tenant-transaction entry point (C3-4). **Built (0004):** `tenant_transaction`, opened for requests by `TenantAPIView` (a base view, not middleware; `ATOMIC_REQUESTS` stays off, D1). It opens the transaction, sets the context and resolves the tenant; the membership check is the `check_principal` hook above.
   - Tenant-owned models are accessed only through the tenant-scoped repository. The repository asserts that the entry point is active and raises otherwise. **Built (0004):** `TenantManager` is the only manager and the base manager of every `TenantOwnedModel`, so reads, writes, related access, `refresh_from_db` and `save()` all raise `TenantContextMissing` outside `tenant_transaction`.
   - Code outside the transaction (auth/session middleware, throttling, post-response hooks) touches platform tables only. `on_commit` callbacks only enqueue work. Streaming responses run one short transaction per poll and never hold a transaction open. (In 0004 `TenantAPIView` refuses streaming responses outright.)
   - Unscoped access to tenant data exists only in migrations (below) and in the future audited platform path (Q5).
3. **Database layer (PostgreSQL Row-Level Security).**
   - Every tenant-owned table has `ENABLE` and `FORCE ROW LEVEL SECURITY` and a tenant policy, with the same expression in `USING` and `WITH CHECK`:
     `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid` (C3-3). A reused connection returns `''`, which `NULLIF` turns into NULL, so the result is 0 rows rather than an error.
   - Context is set only with `SELECT set_config('app.tenant_id', %s, true)`, with a UUID that has already been parsed and validated, passed as a bound parameter (C3-2). `app.user_id` is set the same way. Session-level `SET` and string-built `SET LOCAL` are forbidden.
   - **Built (0004):** the `tenant_isolation` policy (no `TO`, so it binds the migrator too), `ENABLE` + `FORCE` on every tenant table, and a source scan that allows `set_config` and `SET app.*`-style writes only in `rms/tenancy/data/context.py` and `rms/tenancy/data/rls.py`. The only tenant tables so far are the two test-only probe tables.
   - **Identity-scoped membership policy (C3-1a). Planned (0005).** Memberships carry a second, SELECT-only policy:
     `NULLIF(current_setting('app.tenant_id', true), '') IS NULL AND user_id = NULLIF(current_setting('app.user_id', true), '')::uuid`.
     It applies only in identity-plane transactions. It never widens a tenant-plane query. It never allows writes.
   - **Restaurant name and status (C3-1a).** The app role reads only `id`, `name` and `status` of the tenants registry (column grants). Rows are limited, by RLS or a `security_invoker` view, to the current tenant or to tenants in which the `app.user_id` user has a membership. **Built (0004):** column grants and the current-tenant RLS clause. The membership clause is **Planned (0005)**, as a pinned entry on the catalog check's policy allow-list. Because the column grants exclude `created_at`/`updated_at`, never `select_related("tenant")`: the join fails with "permission denied" (a fail-closed 500).
   - **Invite lookup (C3-1c). Planned (0005).** A single reviewed `SECURITY DEFINER` function takes a token hash and returns at most one invitation: its ID, tenant ID, restaurant name, invited email, status and expiry. It has a pinned `search_path` and is owned by a dedicated `NOLOGIN` role. That role has only the needed column grants and `BYPASSRLS`, the written reason being that `FORCE` RLS also applies to the definer. Accepting the invite is a separate write in a tenant-plane transaction for the invite's tenant, after the invited email is matched against the user's verified email (TM-07).
   - **Tenant key rules (C3-9). Built (0004).** The app role cannot UPDATE `tenant_id`. Every unique constraint on a tenant table leads with `tenant_id`. Parents carry `UNIQUE (tenant_id, id)` so that children can use composite FKs. As built, the app role cannot UPDATE `id` either, every tenant table gets `UNIQUE (tenant_id, id)`, and tenant tables have no sequences or identity columns (cross-tenant counters).

## Database roles and credentials (C3-5, C3-6, C3-10)

| Role (illustrative) | Login | Used by | Properties |
|---------------------|-------|---------|------------|
| `rms_migrator` | yes | Migration job only | Owns schema objects. Subject to `FORCE` RLS. `BYPASSRLS` only with a written reason in the change record. **Built** (0003 bootstrap) |
| `rms_app` | yes | API and worker | Not owner, not superuser, no `BYPASSRLS`, not a member of `rms_migrator` or any owner role. DML only, via `ALTER DEFAULT PRIVILEGES`. No UPDATE on `tenant_id`, only INSERT/SELECT on audit tables (TM-18). `statement_timeout` and `idle_in_transaction_session_timeout` set. **Built** (0003); since 0004 also read-only on `django_migrations` and limited to the registry columns above |
| `rms_scheduler` | yes | Periodic scheduler only (C3-8) | SELECT on the `id` and `status` columns of the tenants registry. Can enqueue jobs. No tenant tables. **Planned** (with the first job, 0004 D7) |
| invite-lookup owner | no | Owns the C3-1c function | See above. **Planned** (0005) |

- Migrations run as a **separate job** with a separate DB alias and credentials. Those credentials are absent from the API, worker and scheduler environments, and a CI check of the runtime environment enforces this (R16, TM-29). As built: local and test settings have a `migrator` alias; production settings have only `default` and never read `DB_MIGRATOR_*` (a settings test enforces it). The production migration job and the runtime-environment check are **Planned** (Phase 10, OQ2).
- Data migrations iterate tenants from the registry and set tenant context for each tenant. **Built (0004):** `for_each_tenant(apps, schema_editor, fn)` (`docs/conventions/backend.md`).
- Pooling: transaction pooling is compatible with `set_config(..., true)`. Django persistent connections are allowed only because of the C3-2 reuse test. The C3-2 test is **Built (0004)**; `CONN_MAX_AGE` stays 0 until Phase 10 decides otherwise.
- Maintenance DBs (local/CI bootstrap, **Built 0004**): PUBLIC has no privilege on `postgres` or `template1`; the migrator keeps CONNECT on `postgres` (test and round-trip DB creation); the app role can connect to neither (`make db-check`).

`rms_scheduler` is a separate credential, not a new service or datastore. It exists so that `rms_app` cannot list all tenants (REVIEW: data-engineer + security-engineer).

## Referential integrity across tenants
Tenant-owned rows that reference other tenant-owned rows use composite foreign keys `(tenant_id, x_id) → (tenant_id, id)`. A row therefore cannot point into another tenant, even through a bug. **Built (0004, D5):** the ORM `ForeignKey` uses `db_constraint=False` and the only DB constraint is added by `composite_tenant_fk` (`ON DELETE RESTRICT`). A single-column FK is not enough: RI checks ignore RLS, so it would accept a cross-tenant reference and act as an existence oracle. The same applies to an FK from a platform table into a tenant table, which the catalog check forbids.

## Side channels
- Cache keys, object-storage paths (`tenants/<tenant_id>/…`), realtime channels, job payloads and log context all include `tenant_id`. (Log context: **Built (0004)**, set by `TenantAPIView` only after the path tenant has been resolved, never for rejected requests. The others are **Planned** with their features.)
- Realtime channel names are derived from the resolved tenant, never from connection state or client input (TM-20).
- **Jobs:** the payload carries IDs and `tenant_id` only. Each job runs in one transaction that sets tenant context before any query, and re-reads its data under RLS (TM-24).
- **Cross-tenant periodic work:** the scheduler reads the registry and enqueues one job per tenant (C3-8).

## Platform access (break-glass)
Platform operators do not use tenant endpoints. They use a separate host and cookie with mandatory MFA (ADR-0006 C6-7, Q8). Any cross-tenant capability (support tooling, platform reports) is a separate module and role, fully audited, and designed under `APPROVAL` (Q5).

## Required checks and tests (Phase 2 harness, then every change)
- **CI catalog check (C3-5, R1). Built (0004)** as `rms/tenancy/tests/catalog.py` (full rule list there and in change 0004 C-12). It runs in `make test-backend` (test DB), `make catalog-check` (CI: the dev DB after `make migrate`, read-only, as the app role; zero tenant tables allowed) and at the end of `make migrations-roundtrip`. Each rule has a negative test. Deployed databases: **Planned** (Phase 10; R1 stays open until then). It asserts, among others, that:
  - every tenant table has RLS enabled and forced, plus a policy;
  - the app role is not owner, not superuser, has no `BYPASSRLS`, and is a member of no owner or migration role;
  - every view has `security_invoker = true`;
  - every `SECURITY DEFINER` function is on the reviewed allow-list (in v1, only the C3-1c function);
  - no materialized view covers tenant data;
  - the only `BYPASSRLS` roles are the allow-listed ones.
- **Tests run as the app role (C3-7).** A guard test fails if `current_user` is a superuser or has `BYPASSRLS`. **Built** (0003).
- Two-tenant fixtures by default. **Built (0004):** `two_tenants` with `ISOLATION_DB`.
- Migrations round trip. **Built (0004):** `make migrations-roundtrip` migrates a throwaway DB up, back to zero and up again, then runs the catalog check; each tenant `CreateModel` and its RLS operations must be in the same migration.
- Per endpoint: B's IDs from A's session return 404 with no side effects. A path tenant without membership returns 404. A device bound to A calling B's path returns 409. (**Planned** with the first tenant endpoint; the resolution 404 matrix is built on test views.)
- RLS: without tenant context, queries return 0 rows and writes fail. A connection reused after a tenant request carries no context (C3-2). **Built (0004).**
- Identity plane (**Planned**, 0005): a user sees only their own memberships and those restaurants' name and status. The user-scoped policy adds nothing inside a tenant transaction. Invite lookup returns at most the one matching invite.
- Composite FK: inserting a cross-tenant reference fails at the DB. The same natural key in A and B succeeds in both (TM-17). **Built (0004).**
- Jobs (**Planned**, with the first job): a job for A never reads or writes B. A job without context reads 0 rows.

## Alternatives considered
See ADR-0003: schema-per-tenant (legacy `../rms`, via django-tenants) and database-per-tenant.
