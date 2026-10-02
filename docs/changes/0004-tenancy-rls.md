# 0004 — Tenancy foundation: tenant registry, tenant context, RLS and isolation harness

- **Status:** Open
- **Risk level:** L3 — tenant boundary, RLS policies, DB roles (`docs/process/risk-and-approval.md` escalation triggers). Security review blocking; human approval after design and at acceptance.
- **Requested by / date:** product owner ("push and continue"), 2026-10-01
- **Current gate:** 8 (Testing)
- **Branch:** `feat/0004-tenancy-rls` (based on `feat/0003-scaffold-and-ci`)

## 1. Request
Second Phase 2 change: implement ADR-0003 (accepted, with amendments C3-1..C3-10) as the reusable foundation every tenant-owned feature will build on. No restaurant features, no users, no login (0005), no permission evaluation (0006).

## 2. Requirements
Goal: a developer can add a tenant-owned table and get database-enforced isolation, a tenant-scoped data access path, and a ready two-tenant test harness — and CI fails if any of it is missing.

Acceptance criteria:
1. `tenancy` bounded context (`backend/rms/tenancy/`) with the platform-level restaurant registry: id (UUID), name, status (`active` / `suspended` / `closed`, DB CHECK), timestamps. App role can read only what `tenancy.md` allows (C3-1a column grants); no status changes through the app role.
2. Single tenant-transaction entry point (C3-4): opens a transaction, sets `app.tenant_id` via `set_config(..., true)` with a validated, bound UUID (C3-2); nothing else may set it. Identity-plane equivalent for `app.user_id` exists but its policy users arrive in 0005.
3. Tenant-scoped base model/manager for tenant-owned tables: requires active tenant context and raises if absent; no unscoped default manager (backend conventions "Planned (0004)").
4. A documented, reusable migration pattern (helper) for tenant-owned tables: `tenant_id` NOT NULL, `ENABLE` + `FORCE ROW LEVEL SECURITY`, policy using `NULLIF(current_setting('app.tenant_id', true), '')::uuid` for USING and WITH CHECK, `UNIQUE (tenant_id, id)` for composite-FK parents, tenant-leading indexes, app role cannot UPDATE `tenant_id` (C3-9).
5. A test-only (or minimal internal) tenant-owned table exercised by the harness, proving: no context → 0 rows and writes rejected; tenant A context cannot read/write tenant B rows; cross-tenant composite FK insert fails at DB; reused connection carries no context into the next transaction (C3-2/R13).
6. Tenant resolution from the URL path (`/api/v1/r/<tenant_id>/...`, ADR-0006 C6-1/C6-2): malformed, unknown, non-active and not-permitted tenants all return the same 404, before any tenant data access. Membership validation is a hook that 0005/0006 fill; until then no production route serves tenant data (design decides how to keep this closed).
7. CI catalog check (C3-5): app role not owner/superuser/BYPASSRLS, member of nothing; every tenant table has RLS enabled + forced + a policy; views `security_invoker`; SECURITY DEFINER functions on a reviewed allow-list; no materialized view over tenant data.
8. Carried from 0003: SC-29 (mirror alias flush — isolation tests must not pass on rows left behind); revoke app-role write on `django_migrations`; a real row-write rollback test; revoke PUBLIC CONNECT/TEMP on the `postgres` maintenance DB (low).
9. Two-tenant fixtures/factories (factory_boy if the design adopts it) for every later isolation test.
10. Migrations run as the migrator only; data migrations iterate tenants and set context per tenant (C3-6) — pattern documented even if no data migration exists yet.
11. Docs: `tenancy.md` marks what is built; `conventions/backend.md` tenant section; `testing-strategy.md` isolation suite marked Built.

Out of scope: users, memberships, sessions, invitations (0005); permissions (0006); audit (0007); operator console; scheduler credential and jobs (until the first job exists — design confirms).

Open questions: none known; design may surface some.

## 3. Impact analysis
*(architect, gate 3, 2026-10-01. Risk confirmed **L3**: tenant resolution, tenant-scoped query helpers, RLS policies and DB roles are all L3 triggers (`risk-and-approval.md:18`); tenant resolution and RLS policies are `APPROVAL` (`risk-and-approval.md:36`), so the human approval after design covers 4.D1–D4 and 6.)*

| Area | Effect | Evidence |
|---|---|---|
| Context `tenancy` (new app, existing context) | New: registry model, entry point, scoped base model, RLS migration ops, resolution view base | `domain-model.md:46`; no `backend/rms/tenancy/` yet |
| `rms.core` | Behavior unchanged. `tenant_id_var` gets set (reserved since 0003). New migration `core/0001` (django_migrations lock-down, 6.7) | `rms/core/context.py:15`, `rms/core/logging.py:101` |
| Error handler | Unchanged. Its `set_rollback()` is a no-op without `ATOMIC_REQUESTS`; tenant views roll back themselves (4.D2) | `rms/core/api/errors.py:117`, DRF `views.py:66-69` |
| Settings | `INSTALLED_APPS += rms.tenancy`; test adds the probe app; `ATOMIC_REQUESTS` stays off and is asserted; `CONN_MAX_AGE` stays 0 | `config/settings/base.py:20,47`, `test.py` |
| Routes | No production route added. Route scan gains tenant-route rules | `config/urls.py`, `config/tests/test_routes.py:22` |
| Data | New platform table (registry), two test-only tenant tables, grants/RLS via migrations; no data rewrite | — |
| DB roles / bootstrap | `postgres` DB PUBLIC revoke; app-role writes on `django_migrations` revoked (migration) | `scripts/db/bootstrap.sh` step 3–4; 0003 §9 follow-ups 1–2 |
| Test harness | Isolation fixtures, SC-29 enforcement, factory_boy (dev dep) | `conftest.py`, `config/tests/db_guards.py`, 0003 §5.2 (mirror never flushed **and** never wrapped in a test atomic: `django/test/testcases.py:1152,1417` `include_mirrors=False`) |
| CI | Catalog check runs inside `make test-backend`; `migrations-check` also on test settings; new migration round-trip step | `.github/workflows/ci.yml`, `Makefile` |
| API contracts | None public. Tenant-path shape fixed (`/api/v1/r/<uuid>/…`, `api.md:17`) for test views only | `docs/conventions/api.md:11-24` |
| Permissions | None added (catalog untouched); views still declare `permission_classes` (DenyAll default) | `authorization.md`; `base.py` `REST_FRAMEWORK` |
| Audit / jobs / UI | None (no auditable action, no job, no screen) | — |
| Docs to update | `tenancy.md` (Built marks), `conventions/backend.md` tenant + tests sections, `testing-strategy.md:21,26,48`, `data.md` (registry), `README` none | — |
| Backward compat | Nothing deployed; no external client | — |

Must **not** change: the 0003 error envelope and `set_rollback` call; `DenyAll` default and `PUBLIC_ROUTES`; `CONN_MAX_AGE = 0` (raising it is Phase 10, now unblocked by the C3-2 test); production settings (no migrator alias; migration-job settings are Phase 10); permission catalog; ADR-0003/0006 text (Accepted). Unknowns: none found by grep for dynamic `set_config`/`current_setting` use (no hits outside docs).

## 4. Architecture decision
Implements Accepted ADR-0003 (C3-1..C3-10) and ADR-0006 C6-1/C6-2; no new ADR — every choice below stays inside them. No new context, service or datastore.

- **D1 Entry point is explicit, not `ATOMIC_REQUESTS`** — `APPROVAL` (tenant resolution). `tenant_transaction(tenant_id: UUID)` opens `transaction.atomic(using="default", durable=True)`. `durable=True` makes it the outermost transaction (Django raises if nested), so a tenant can never be switched or nested mid-transaction; Django's TestCase atomics are exempt by design (`_from_testcase`). Rejected: `ATOMIC_REQUESTS` — it wraps every view (health, future identity plane) and opens the transaction *before* the tenant is known, and with `durable` it would make every tenant view fail. A settings test asserts `ATOMIC_REQUESTS` is false on `default`.
- **D2 Rollback on error responses at the view boundary** — `REVIEW`. DRF turns exceptions into responses *inside* `dispatch`, so the atomic block would commit them. `TenantAPIView.dispatch` marks rollback for every response with status ≥ 400 and renders the response inside the block (nothing lazy escapes the transaction). The 0003 handler stays as is.
- **D3 Membership hook is a closed method, filled by subclassing in `access`** — `APPROVAL` (tenant resolution). `tenancy` must not import `access` (`domain-model.md:47`). `TenantAPIView.check_principal(request, tenant)` raises the uniform 404 by default. 0005/0006 add `access.api.MemberTenantAPIView` that overrides it; feature views subclass that. Rejected: a registered callable (hidden global). Closed until then by (a) no tenant route in `config/urls.py`, (b) a route-scan rule, and (c) a test that fails if `check_principal` is overridden outside `*.tests.*` modules or an allow-list (empty in 0004).
- **D4 Registry RLS: `ENABLE` without `FORCE`** — `APPROVAL` (RLS policy) with security-engineer. The registry is platform-level, owned by the migrator (trusted, migration job only). Without `FORCE`, the migrator (data migrations, test fixtures) sees all rows, and the app role sees only `id = current tenant` through a `FOR SELECT` policy with column grants on `id, name, status`. Alternative: `FORCE` plus a role-targeted migrator policy (`TO <migrator>`). Rejected for now: it needs role names in policies and a policy allow-list entry, and gives no protection against the table owner. The C3-1a membership clause is added to this policy in 0005.
- **D5 Composite FKs by migration op, ORM FK with `db_constraint=False`** — `REVIEW`. Django 5.2 has no composite FK. The ORM `ForeignKey` keeps joins. The only DB constraint is `(tenant_id, x_id) → parent (tenant_id, id) ON DELETE RESTRICT`, added by a reusable op. A catalog test proves that every tenant→tenant FK column is covered.
- **D6 Test-only tenant tables in a test-only app** — `REVIEW`. No business table may exist without requirements. The probe app is installed only in `config.settings.test` and never reaches dev or prod DBs.
- **D7 Scheduler credential deferred** — `REVIEW`. There is no job until a feature needs one (C3-8). `tenancy.md` keeps `rms_scheduler` marked Planned.
- **D8 IDs: UUIDv4 for the registry** — `REVIEW`. Python 3.12 and PG16 have no native v7, and locality does not matter for a small table. v7 for high-volume tables is decided with the first one (data-engineer).

## 5. Security analysis
*(security-engineer, gate 5, Mode 1, 2026-10-01. Inputs: §2–4 and §6; ADR-0003 C3-1..C3-10; ADR-0006 C6-1/C6-2; `tenancy.md`; `security.md` TM-08/10/13/17/24/25/28/29/41; risks R1, R11–R13, R16; code at `e0d82be`. Items marked **verified** were reproduced on the local `postgres:16` container in a scratch database that was dropped afterwards. **Verdict: PROCEED WITH CONTROLS** (5.7).)*

### 5.1 Assets, actors, entry points
- **Assets:** tenant rows (only the probe tables in 0004, all operational data later); the registry, which is the customer list; the RLS, grant and role configuration itself (R1); `django_migrations`, which records which RLS operations have been applied; the trustworthiness of the isolation suite (R12, SC-29); availability.
- **Actors:**
  - an anonymous client sending any path;
  - a member of A probing B (from 0005; the design must already hold);
  - a member of a suspended or closed tenant;
  - **a developer adding a feature.** This is the most likely source of a bypass: a forgotten filter, an extra manager, raw SQL, a table without RLS, a test that cannot fail;
  - a compromised app process holding only the app-role credentials (R16);
  - the migration job (trusted, never present at runtime);
  - a compromised dev dependency (factory_boy).
- **Entry points:**
  - E1: `/api/v1/r/<uuid>/…` through `TenantAPIView` (test-only in 0004);
  - E2: `tenant_transaction` / `identity_transaction`;
  - E3: `TenantManager`/QuerySet and `save()`;
  - E4: migrations run as the migrator (RLS ops, `for_each_tenant`, `core/0001`);
  - E5: `bootstrap.sh` (superuser);
  - E6: the test harness (fixtures, flush, guards);
  - E7: CI (catalog check, round-trip);
  - E8: code outside the transaction (middleware, `on_commit`, signals, management commands, shell).

### 5.2 Verified facts that change the design
- **F1. TestCase atomics do wrap mirrors.** The design's evidence is wrong on this point (§3 "Test harness" row, §6.8).
  - `_enter_atomics` iterates `_databases_names()` with `include_mirrors=True` (`django/test/testcases.py:1384`). Only post_migrate, fixtures and flush skip mirrors (`:1152, :1256, :1417, :1472`).
  - So in a non-transactional test, the durable `tenant_transaction` is only a savepoint, because `_from_testcase` is exempt (`django/db/transaction.py:186-188`).
  - **Verified:** `set_config(…, true)` survives `RELEASE SAVEPOINT`. Tenant A therefore stays set for the rest of the test after the block exits. → C-1(d), C-2.
- **F2. Flush does not drop DDL.** §6.9 says the checker's negative tests are "cleaned up by the flush". That is wrong: flush truncates model tables only, so a view, function, policy or extra table created by a test stays for the whole session. → C-13.
- **F3. A single-column FK between tenant tables is a cross-tenant link and an existence oracle.** **Verified:**
  - under A's context, A sees 0 of B's parent rows;
  - yet an INSERT with a single-column FK to B's parent succeeds, because RI checks bypass RLS;
  - the composite FK rejects the same insert.

  The same oracle exists for any FK from a platform table into a tenant table. → C-12(5).
- **F4. A migrator read of a FORCE table without context is vacuous.** `tenant_isolation` has no `TO`, so it binds the migrator too. Any "no row left" or "B unchanged" assertion made through `migrator` without context passes whatever the data. → C-14.
- **F5. Column grants versus ORM joins.** **Verified:** a join that selects `tenancy_restaurant.created_at` fails with `permission denied for table`. `.only()` on the manager does not apply to `select_related("tenant")`, so that call returns a 500. This fails closed and is acceptable (C-10).
- **F6. Large objects.** **Verified:** the app role can call `lo_create`, and large objects have no RLS. Nothing uses them; the catalog keeps the count at zero (C-12(11)).
- **F7. The round-trip target endangers the dev DB.** Outside the test runner, `config.settings.test` connects to `DB_NAME`, the dev DB (`TEST` applies only inside the runner).
  - Run with test settings, the round-trip installs the probe tables in the dev DB, which contradicts D6.
  - Run with local settings, it cannot exercise the probe app.
  - Either way, `migrate <app> zero` destroys a developer's local data. → C-17.
- **F8 (confirms the design).**
  - DRF runs `initial()` before looking up the handler (`rest_framework/views.py:514-519`), so neither 405 nor OPTIONS can answer before resolution.
  - The `uuid` converter accepts lower case only (`django/urls/converters.py:29`).
  - No `django.contrib` app is installed (`config/tests/test_routes.py:312`), so there is no admin and no contenttypes signal path.

### 5.3 Threats
| ID | Entry | Threat (STRIDE; OWASP API) | L/I | Control | Test |
|---|---|---|---|---|---|
| T4-01 | E1 | Path tenant that is unknown, suspended, closed, not permitted or malformed serves data or reveals that it exists (I; API1, TM-08) | H/C | D3 always-deny; resolution inside the transaction; C-5, C-6 | N-01, N-02 |
| T4-02 | E1 | Headers, body bytes or query count differ between unknown, suspended and active-but-not-member tenants; timing differs (I) | M/L | C-6; timing is residual RR-1 | N-01 |
| T4-03 | E1 | Hook opened by accident before 0005/0006: a subclass overrides `check_principal`, `initial` or `dispatch`, a tenant route reaches `config/urls.py`, or a route uses `<str:tenant_id>` (E; API5) | M/C | C-5 | N-02 |
| T4-04 | E2 | Context set by another path: string-built `SET LOCAL`, session `SET`, `ALTER ROLE/DATABASE … SET app.*`, libpq `-c` options (T/I; R13) | M/C | C-3, C-12(6), C-18 | N-03, N-07 |
| T4-05 | E2 | Context leaks: reused connection (R13), savepoint nesting (F1), `on_commit`, a thread or async task copying the contextvar (I) | M/C | C-1, C-2 | N-04 |
| T4-06 | E2 | Tenant nested or switched mid-transaction; identity and tenant planes mixed (T; TM-40) | L/C | D1 durable; C-1(a,f) | N-05 |
| T4-07 | E3 | App-layer bypass: extra or unscoped manager, `raw()`, `extra()`, cursor SQL, `QuerySet(model=…)`, M2M auto-through tables, `bulk_create` without a tenant (I/T; API1) | H/H (RLS still holds) | C-7, C-8, C-9 | N-06 |
| T4-08 | E3/E4 | Tenant table without ENABLE/FORCE/policy, an extra permissive policy, or a wrong expression (I; R1, TM-28) | M/C | C-12 | N-07 |
| T4-09 | E3 | Cross-tenant reference through a single-column FK or a platform→tenant FK, giving a link plus an existence oracle (T/I; TM-10/17) | M/H | D5; C-12(5) | N-08 |
| T4-10 | E3 | Unique or exclusion constraint, a global PK or a sequence used as a cross-tenant oracle or counter (I; TM-17) | M/M | C-12(4,11); C-16 | N-09 |
| T4-11 | E3 | `tenant_id` or `id` rewritten by mass assignment (T; TM-13, C3-9) | M/C | Column grants; C-7(c,d); C-11 | N-10 |
| T4-12 | E4 | `restrict_tenant_key_update` grants to the wrong role, or `DB_APP_USER` is wrong or unset in the migration job, so the prod app keeps table-level UPDATE (E) | M/H | C-11 | N-10 |
| T4-13 | E4 | `for_each_tenant` silently does nothing (non-atomic migration) or touches another tenant (T/I) | L/H | C-15 | N-11 |
| T4-14 | E4 | App role writes `django_migrations` to mark an RLS migration as applied (T/E; 0003 follow-up 1) | L/C | §6.7 `core/0001`; C-12(10) | N-12 |
| T4-15 | Registry | App reads all tenants or ungranted columns, or changes status (I/E; C3-1a) | M/H | D4; C-12(10); C-10 | N-13 |
| T4-16 | E5 | PUBLIC CONNECT/TEMP on the `postgres`/`template1` DBs (I) | L/L | §6.7; C-19 | db-check |
| T4-17 | DB | Definer function, non-invoker view, matview, trigger, extension, foreign table, other schema or large object bypasses RLS (E/I; TM-28/41) | L/C | C-12(1,7,8,11) | N-07 |
| T4-18 | DB | Role drift: BYPASSRLS, membership in predefined roles (`pg_read_all_data`/`pg_write_all_data` ignore grants), ownership, `rolconfig` (E; R12) | L/C | C-12(6,9) | N-07 |
| T4-19 | E6 | Tests that cannot fail: superuser (R12), leftover rows (SC-29), migrator reads under FORCE (F4), no positive control (false assurance) | H/H | C-2, C-13, C-14, C-20 | N-14 |
| T4-20 | E1 | D2: partial write committed on a 4xx; a 2xx returned after an aborted transaction; streaming or lazy content run outside the transaction (T/I; TM-25) | M/H | C-4 | N-15 |
| T4-21 | E8 | Middleware, `on_commit`, signals, management commands or shell read tenant data (I; TM-25) | M/M | Fail-closed manager plus RLS; C-1(c); no admin (F8) | N-04, N-06 |
| T4-22 | E7 | Migrator alias used from app code; migrator credentials at runtime (E; R16, TM-29) | L/C | C-9(b), C-18 | N-16 |
| T4-23 | E7 | Round-trip destroys or pollutes the dev DB (D/T) | M/M | C-17 | CI |
| T4-24 | E1 | Log context carries the unvalidated path tenant for rejected requests (R) | L/L | C-1(g) | — |
| T4-25 | — | Repudiation of registry or fixture writes | L/L | Not applicable in 0004: there is no product write path, registry writes are migrator-only (C-12(10)), and audit is 0007 | — |
| T4-26 | E1 | Transaction held during render; slow requests (D; API4) | L/M | Role `statement_timeout` 15 s and `idle_in_transaction_session_timeout` 30 s (`bootstrap.sh:60-61`, C-12(6)); no list endpoint in 0004 | — |
| T4-27 | E6 | factory_boy supply chain | L/M | Dev group, locked with hashes, `pip-audit`; imported only in tests (C-9(b)) | audit |

**Replay and race (L3).**
- Replay is not applicable: 0004 has no business command and no state-changing production endpoint.
- Race between tenants: the context is local to each transaction and each connection, and pooled reuse is covered by C3-2 (N-04).
- Tenant suspended mid-request: the status is read inside the request's transaction snapshot, so suspension takes effect on the next request, which matches TM-05.

### 5.4 Required controls (amendments to §6)
- **C-1 (§6.3) `tenant_transaction`:**
  - (a) Preconditions:
    - `type(tenant_id) is uuid.UUID`; a `str`, `None` or a subclass raises `TypeError` before any SQL.
    - `connections["default"].get_autocommit()` is true.
    - Every enclosing atomic is `_from_testcase`.
  - (b) The first statement is `SELECT current_setting('app.tenant_id', true), set_config('app.tenant_id', %s, true)`. If the previous value is non-empty, raise `TenantContextActive`: this detects any leak.
  - (c) Set `_active_tenant` (tenant UUID plus the outermost `Atomic` object) only after `set_config` succeeds. Reset all contextvar tokens in a `finally` **inside** the atomic block, so that `on_commit` callbacks and code after the block run without context.
  - (d) On normal exit, while still inside the atomic block, run `set_config('app.tenant_id', '', true)`. This closes the F1 savepoint case. Skip it if `needs_rollback` is set, because the rollback restores the value.
  - (e) `current_tenant_id()` also checks that the stored `Atomic` is still in `connections["default"].atomic_blocks`.
  - (f) `identity_transaction` applies (a)–(e) to `app.user_id` and is durable. Each entry point raises if the other plane's setting or contextvar is set: the C3-1a guard depends on the planes never mixing.
  - (g) Recommended (low): set `tenant_id_var` only after `resolve_active_tenant` succeeds.
- **C-2 (§6.8) Context-sensitive tests are transactional.** These tests use `ISOLATION_DB`: C3-2, the D2 rollback tests, NT-08, `for_each_tenant`, and every two-tenant test. In TestCase mode, migrator-created registry rows are invisible to `default`, so two-tenant tests cannot work there anyway. A non-transactional unit test proves C-1(d).
- **C-3 (§6.3) Source scan.**
  - Case-insensitive patterns, scanned over `backend/**/*.py` (migrations included) and `scripts/**`:
    - `set_config\s*\(`
    - `\bset\s+(local\s+|session\s+)?app\.`
    - `\balter\s+(role|user|database)\b[^;]*\bset\s+app\.`
    - `-c\s*app\.`
  - Exact-path allow-list:
    - `rms/tenancy/data/context.py`
    - `rms/tenancy/data/rls.py`
    - `rms/core/tests/views.py`, for the `rms.rollback_probe` setting only. It contains no `app.` write.
  - The scan has a self-test with one sample string per pattern.
- **C-4 (§6.6) D2 `dispatch`:**
  - (a) Status ≥ 400: call `transaction.set_rollback(True, using="default")`.
  - (b) Status < 400 while `connections["default"].needs_rollback` is set: raise, so the client gets a 500 and never a 2xx for work that did not commit.
  - (c) A streaming response (`response.streaming`) raises `ImproperlyConfigured`, which gives a 500 and a rollback. Call `render()` only on an unrendered `SimpleTemplateResponse`.
  - (d) No catch-all: an unhandled exception leaves the `with` block, so the transaction rolls back and Django returns its 500.
- **C-5 (§6.6) D3 closure, extended:**
  - (a) `dispatch`, `initial`, `resolve_active_tenant` and `check_principal` are marked `@typing.final`; mypy strict enforces it.
  - (b) The override test imports every module under `rms` and `config` with `pkgutil.walk_packages`, then walks the `TenantAPIView` subclasses recursively.
    - It fails on any class outside `ALLOWED_OVERRIDES` (empty in 0004; `rms.access.api` in 0005) and outside `.tests.` packages that defines any of `{dispatch, initial, resolve_active_tenant, check_principal, as_view}`.
    - An AST scan of the same method names in non-test modules also catches modules that are never imported.
  - (c) Route scan rules:
    - Every pattern that contains `tenant_id` is exactly `api/v1/r/<uuid:tenant_id>/…`, maps to a `TenantAPIView` subclass and declares a non-`AllowAny` permission.
    - A `TenantAPIView` routed without `<uuid:tenant_id>` fails.
    - `config.urls` has zero tenant routes in 0004 (an explicit count test).
  - (d) The tenant comes only from `self.kwargs["tenant_id"]`.
- **C-6 (§6.6/§6.8 NT-08) Identical 404:**
  - **Group R** (resolved in the view: unknown, suspended, closed, active with the closed hook):
    - identical status;
    - identical raw body bytes after the `request_id` value is removed;
    - identical header names and values except `X-Request-ID`;
    - identical number of queries on `default`, and no captured SQL touches a tenant table.
  - **Group M** (malformed, upper-case, non-UUID): same status and same parsed `code`/`message` as group R. The raw bytes may differ (JsonResponse versus the DRF renderer); this is accepted because the client chose the malformed value.
  - Each case is run with GET, with a POST whose body is invalid (it must give 404, never 400) and with an unsupported method (404, never 405).
  - **Handover to 0005:** the membership lookup must use the same queries whether the tenant is active or not.
- **C-7 (§6.4) `TenantQuerySet`/`save()` hardening:**
  - (a) `raw()` and `extra()` raise.
  - (b) `bulk_create` fills `tenant_id` from context and raises on a mismatch, the same rule as a `save()` insert.
  - (c) `update()`/`bulk_update()` raise on the app side if `tenant` or `tenant_id` is among the fields; the DB also denies it.
  - (d) `save()` decides insert versus update by `_state.adding`. On update, `update_fields` excludes `tenant` and `id`, and an explicit `update_fields` that contains `tenant` raises.
- **C-8 (new) Model-introspection test.** For every concrete `TenantOwnedModel`:
  - `_meta.managers` is exactly one `TenantManager`, and `_meta.base_manager` and `_meta.default_manager` are `TenantManager`;
  - there is no M2M with an auto-created `through`;
  - every FK or OneToOne to another `TenantOwnedModel` has `db_constraint=False` and a matching composite constraint (C-12(5));
  - only the inherited `tenant` field references `Restaurant`;
  - every other concrete model is on the platform allow-list (`Restaurant`).
- **C-9 (new) Scans:**
  - (a) In non-test `rms/**` modules, `.raw(`, `.extra(`, `RawSQL(`, `QuerySet(`, `connection.cursor(` and `connections[…].cursor(` appear only in `rms/tenancy/data/*.py` and `rms/core/health.py`.
  - (b) The `migrator` alias (`using(`, `connections[`, `db_manager(`, `database=`) and `factory` imports appear only in `conftest.py`, `config/tests/**` and `rms/**/tests/**`.
- **C-10 (§6.2) Registry.** A test proves that `select_related("tenant")` fails closed and never returns `created_at`. `conventions/backend.md` says never to `select_related` the tenant.
- **C-11 (§6.5/§6.7) Role-name composition** in `restrict_tenant_key_update` and `core/0001`:
  - (a) `RMS_DB_APP_ROLE = env.require_str("DB_APP_USER")`, with no default, checked against the bootstrap regex.
  - (b) Before granting: the role exists, is not `current_user`, and has neither `rolsuper` nor `rolbypassrls`, else the migration fails.
  - (c) After the forward grants, it asserts that `has_table_privilege(role, t, 'UPDATE')` is false and that `has_column_privilege(role, t, 'tenant_id'|'id', 'UPDATE')` is false, else it fails.
  - (d) `updatable_columns` rejects `id` and `tenant_id`.
  - (e) Names are composed only with `sql.Identifier`; tables come from the historical model's `_meta.db_table`.
- **C-12 (§6.9) Catalog check, amended.** It is parameterised by the app role name instead of `current_user`, so that C-13 can run it as the migrator.
  1. **Scope.**
     - All namespaces except `pg_catalog`, `information_schema` and the toast/temp namespaces. Any namespace other than `public` fails.
     - Relkinds `r, p, v, m, f, S` are inspected. Foreign tables fail.
     - Partitions are checked individually.
     - A table counts as a tenant table if it has a live `tenant_id` column (`attnum > 0 AND NOT attisdropped`).
  2. **Tenant tables:**
     - `tenant_id` is `uuid NOT NULL`;
     - RLS is enabled and forced;
     - there is exactly one policy, `tenant_isolation`: `polcmd '*'`, `polpermissive`, roles `{0}` (PUBLIC), and `qual = with_check =` the pinned literal.

     Policy allow-list for the whole DB: tuples of (table, name, cmd, permissive, roles, qual, with_check). Any other policy fails, whether permissive or restrictive and whatever its roles.
  3. **Privileges.**
     - The app has no `TRUNCATE`/`REFERENCES`/`TRIGGER` on any relation and no UPDATE on `tenant_id` or `id` of any tenant table.
     - PUBLIC holds no relation privilege.
     - The app has no CREATE on any schema and no CREATE/TEMP on the database.
  4. **Uniqueness.** Every unique constraint, unique index (including partial and expression indexes) and exclusion constraint other than the PK leads with `tenant_id`. The PK is `id` alone.
  5. **Foreign keys.**
     - Every FK into a tenant table comes from a tenant table and pairs `tenant_id` with `tenant_id` (`conkey`/`confkey`).
     - Every tenant table has an FK `(tenant_id) → tenancy_restaurant(id)`; the C-20(b) guard depends on it.
     - No FK goes from a non-tenant table into a tenant table.
  6. **Roles.**
     - The app role has none of `rolsuper`, `rolbypassrls`, `rolcreaterole`, `rolcreatedb`, `rolreplication`, `rolinherit`.
     - `pg_has_role(app, r.oid, 'MEMBER')` is false for every other `pg_roles` row, including the predefined `pg_*` roles and the migrator.
     - The app owns nothing in `pg_class`, `pg_namespace`, `pg_proc`, `pg_type`, `pg_database` or `pg_largeobject_metadata`.
     - `rolconfig` contains both timeouts and nothing matching `app.%`, `row_security=%`, `search_path=%`, `role=%` or `session_authorization=%`.
     - `pg_db_role_setting` for this DB has no `app.%` entry for any role.
  7. **Views.** No view without `security_invoker=true` in any schema; no materialized view anywhere.
  8. **SECURITY DEFINER.** Functions and procedures (`prokind f,p`) must equal the allow-list of (`oid::regprocedure`, owner, `md5(prosrc)`, `proconfig`, `proacl`); empty in 0004. `ALTER FUNCTION … SET search_path` and `OWNER TO` leave `prosrc` unchanged, which is why the tuple includes the other fields.
  9. **BYPASSRLS.** Non-superuser roles with `rolbypassrls`: empty allow-list.
  10. **Registry and `django_migrations`.**
      - Registry: `relrowsecurity` true and `relforcerowsecurity` false (pinned); owner is the migrator; the app has no table-level privilege, has SELECT on exactly `{id, name, status}` and has no column-level INSERT/UPDATE.
      - `django_migrations`: the app has SELECT only.
      - No other non-owner role holds privileges on either table.
  11. **New rules:**
      - extensions are exactly `{plpgsql}`;
      - no user triggers (`NOT tgisinternal`) and no event triggers;
      - `pg_largeobject_metadata` is empty;
      - no sequences or identity columns on tenant tables, because they are cross-tenant counters (D8);
      - the migrator's `pg_default_acl` equals the bootstrap set and grants nothing to PUBLIC.
  12. **Where it runs.**
      - In `make test-backend` against the test DB.
      - In CI against the dev DB after `make migrate`, through a read-only entry point. There, zero tenant tables is allowed and every other rule applies.
      - Against deployed DBs in Phase 10 (follow-up; R1 stays open until then).
- **C-13 (§6.9) Checker negative tests.**
  - Each case runs in `transaction.atomic(using="migrator")`, always rolled back, and calls `catalog_failures(alias="migrator", app_role=…)` inside the same transaction. The flush is not relied on (F2).
  - Each of these must be reported:
    - a tenant table without FORCE;
    - a tenant table without a policy;
    - a second permissive policy;
    - a policy `TO <app>`;
    - a policy with an altered qual;
    - a non-invoker view;
    - a matview;
    - an unlisted definer function;
    - an allow-listed definer whose `proconfig` changed;
    - a unique constraint not leading with `tenant_id`;
    - a single-column tenant→tenant FK;
    - a platform→tenant FK;
    - `GRANT TRUNCATE` to the app role;
    - `GRANT UPDATE (tenant_id)` to the app role;
    - a table in a new schema;
    - an unlisted non-tenant table;
    - a trigger.
  - A final assertion shows the real check is clean, with no residue.
- **C-14 (§6.8) Non-vacuous assertions.**
  - Add the helper `rows_visible_to(tenant_id, model)`. It counts under that tenant's context: `tenant_transaction` on `default`, or `set_config` on the migrator inside an atomic block.
  - Every "no row", "B unchanged" or "rollback left nothing" assertion uses it, paired with a positive control in the same test.
  - Tests never SELECT a tenant table through the migrator without context (F4).
  - The C3-2 test asserts a count > 0 under A before it asserts 0 afterwards.
- **C-15 (§6.5) `for_each_tenant`:**
  - it raises unless `schema_editor.connection.in_atomic_block`;
  - IDs are bound as parameters;
  - the setting is cleared in `finally`;
  - registry reads use only `schema_editor.connection`;
  - `fn` filters explicitly.
- **C-16 (D8).** PKs are server-generated. Tenant-model serializers never accept `id` on create, because a global PK collision is an oracle. Recorded in `conventions/backend.md`.
- **C-17 (§6.10) `migrations-roundtrip`.**
  - It runs only on a dedicated throwaway DB, for example `rms_roundtrip`: created by the migrator from `rms_template`, ACL locked down like the test DB, and dropped at the end.
  - It refuses to run if the target equals `DB_NAME` or lacks the fixed prefix.
  - It never touches the dev DB.
  - It ends with the catalog check.
  - A migration-graph test asserts that each tenant `CreateModel` and its `enable_tenant_rls` are in the same migration, so a partial reverse cannot leave a table without RLS.
- **C-18 Settings tests:**
  - `ATOMIC_REQUESTS` is false on every alias;
  - `DATABASES["default"]["OPTIONS"]` has no `options` key;
  - `CONN_MAX_AGE` stays 0;
  - production `DATABASES` keys are exactly `{"default"}`, and production settings never read `DB_MIGRATOR_*`;
  - the probe app is absent from local and production `INSTALLED_APPS`.
- **C-19 (§6.7) Bootstrap.**
  - `db-check` additionally asserts that the `postgres` datacl has no PUBLIC entry and that `has_database_privilege(app, 'postgres', 'CONNECT')` is false.
  - Recommended (low, data-engineer): the same revoke on `template1`.
  - The existing `pg_isready` healthcheck needs no CONNECT, and test-DB creation keeps the migrator's CONNECT.
- **C-20 (§6.8) SC-29 extension:**
  - (a) The autouse guard covers every transactional route: `django_db(transaction=True)`, the `transactional_db`, `live_server` and `django_db_serialized_rollback` fixtures, and unittest `TransactionTestCase` that is not a `TestCase`. Each must include `migrator`.
  - (b) The empty-registry guard is valid only because of three things: D4 (no FORCE), C-12(5) (an FK to the registry on every tenant table) and C-12(10) (no app INSERT on the registry). The harness docstring records this, and a change to any of the three must change the guard. Under FORCE without a migrator policy, the guard and `for_each_tenant` would both become vacuous.
  - (c) The proof test: test 1 commits A plus probe rows and stores A's UUID. Test 2 asserts that the registry is empty **and** that `rows_visible_to(old_A, ProbeParent) == 0`.

### 5.5 Rulings
- **D1 (APPROVAL): accept**, with C-1, C-2, C-4(c), C-9(b) and C-18. Durable outermost transaction plus a fail-closed manager plus FORCE RLS leaves no path outside the entry point that returns tenant rows:
  - middleware, `on_commit`, signals after commit, management commands, shell and loaddata/dumpdata all raise in the manager and get 0 rows from RLS;
  - migrations use historical plain managers under FORCE RLS;
  - admin is not installed.
- **D2 (REVIEW): accept**, with C-4.
- **D3 (APPROVAL): accept**, with C-5. The three closure checks are not enough on their own: overriding `initial` or `dispatch` bypasses `check_principal` as surely as overriding it does.
- **D4 (APPROVAL): accept ENABLE without FORCE** on the registry, pinned by C-12(10). Reasons:
  - FORCE gives no protection against the owner, who can run `NO FORCE`.
  - The migrator is trusted and absent at runtime (R16).
  - The app-role protection is identical under both options: SELECT policy for the current tenant only, three column grants, no DML.
  - FORCE would need an env-dependent role name inside a policy. Without that policy it would make C-20(b) and `for_each_tenant` silently vacuous.

  Revisit in 0005, when the C3-1a clause (and later the `rms_scheduler` policy) arrives. Each must be a pinned entry on the policy allow-list.
- **D5 (REVIEW): accept**, with C-8 and C-12(5). F3 shows that the composite FK is the control itself, not merely defence in depth.
- **D6 (REVIEW): accept**, with C-17 and C-18.
- **D7 (REVIEW): accept.** No job code in 0004. The role allow-lists make adding the scheduler a reviewed change.
- **D8 (REVIEW): accept**, with C-16 and C-12(11).
- **§6.5 role names: accept** `DB_APP_USER` from the environment, with C-11.
- **§6.7: accept**, with C-19.
- **§6.9 allow-lists:** as defined in C-12, all empty except the registry policy, `{django_migrations, tenancy_restaurant}` and `{plpgsql}`.

### 5.6 Required negative tests (for the QA plan, in addition to §6.8)
- **N-01** C-6 matrix.
- **N-02** C-5 checks:
  - self-tests: a synthetic subclass in a non-test module name is flagged; a `<str:tenant_id>` route is flagged; a `TenantAPIView` routed without a tenant is flagged;
  - the default hook gives 404 for an active tenant.
- **N-03** C-3 scan self-tests.
- **N-04** Context leaks, all transactional:
  - C3-2 for `app.tenant_id` and `app.user_id`, with a positive control;
  - an `on_commit` callback querying `ProbeParent` raises and a raw count returns 0;
  - the setting is `''` after exit in TestCase mode;
  - a planted leaked setting makes entry raise `TenantContextActive`;
  - a new thread with a copied context gets `TenantContextMissing`.
- **N-05** Nesting and arguments:
  - A in A, B in A, identity in tenant and tenant in identity all raise;
  - `str`, `None` and UUID-subclass arguments raise before any SQL.
- **N-06** Manager:
  - **Outside context**, each of these raises `TenantContextMissing`: `all`, `filter`, `get`, `values`, `count`, `aggregate`, `exists`, `in_bulk`, `iterator`, `update`, `delete`, `bulk_create`, `bulk_update`, `get_or_create`, `raw`, `extra`, related access in both directions, `refresh_from_db`, and `save()` update.
  - **Under A**, against B's IDs:
    - `get` raises `DoesNotExist`;
    - `pk__in` returns nothing;
    - `update` and `delete` affect 0 rows, and B is unchanged (C-14);
    - `bulk_create` with `tenant_id=B` raises in the app, and a raw insert is rejected by WITH CHECK;
    - `select_related("tenant")` fails closed.
- **N-07** C-13 cases.
- **N-08** A cross-tenant composite FK insert **and update** fail at the DB, both through the ORM with app checks bypassed and through raw SQL.
- **N-09**
  - The same `code` in A and B succeeds.
  - A duplicate in A fails.
  - The response carries no constraint name.
- **N-10** Tenant key and role checks:
  - app-role `UPDATE … SET tenant_id` and `UPDATE … SET id` raise `InsufficientPrivilege`;
  - `save(update_fields=["tenant"])` raises;
  - the C-11 checks fail for an unknown role, the migrator's own name and an unset variable.
- **N-11** `for_each_tenant`:
  - it raises in a non-atomic migration;
  - each tenant sees only its own rows;
  - the setting is `''` afterwards.
- **N-12** App-role INSERT, UPDATE, DELETE and TRUNCATE on `django_migrations` are denied.
- **N-13** Registry, as the app role:
  - no context → 0 rows;
  - under A → only A;
  - B by ID under A → 0 rows;
  - `created_at` → denied;
  - INSERT, `UPDATE status` and DELETE → denied.
- **N-14** Harness:
  - the C-20(a) guard self-test, calling the guard function directly;
  - the C-20(c) test pair;
  - the existing session guards still pass.
- **N-15** D2 matrix:
  - a 201 commits, and the row is visible under A;
  - a write followed by `ValidationError`, `NotFound`, `PermissionDenied` or an explicit `Response(status=409)` leaves no row (C-14);
  - a write followed by an unhandled error gives 500 and leaves no row;
  - a swallowed DB error with `needs_rollback` gives 500, not 2xx;
  - a streaming response gives 500 and leaves no row.
- **N-16** C-18 settings tests and the C-9(b) scan.

### 5.7 Residual risk and verdict
- **RR-1 (low).** Timing can tell an unknown tenant from an existing one. UUIDv4 cannot be enumerated, TM-08 treats the UUID as non-secret, and C-6 fixes headers, body and query count. **Proposed for `docs/risks.md` if the human accepts it.**
- **RR-2.** The migrator/owner is fully trusted: it can turn FORCE off and reads the whole registry. This is existing R16, mitigated by keeping it out of runtime.
- **RR-3.** Until Phase 10 runs the catalog check on deployed DBs (C-12(12)), it proves the CI and dev DBs only. R1 stays open.
- **RR-4.** App-layer gaps that remain behind RLS: `QuerySet(model=…)` construction and cursor SQL in the allow-listed modules. These are limited by the C-9 scans.
- **RR-5.** Fail-closed 500s (`select_related("tenant")`, deferred registry columns) affect availability and developer experience, not exposure.

**Verdict: PROCEED WITH CONTROLS.** No BLOCK condition is met by the design as amended. Every tenant query needs context at both the app layer and the DB layer, no endpoint lacks a permission, nothing builds SQL from input, no secret is involved, and no token is JS-readable. The verdict holds only if all of the following are true:
1. C-1..C-20 are folded into §6.
2. The human approval of D1, D3, D4 and §6 (APPROVAL, `risk-and-approval.md:36`), with these controls, is recorded in this change record **before** implementation.
3. At gate 9, any of C-1, C-4, C-5, C-11, C-12, C-14 or C-20 that is missing or untested is `high` and blocks.

## Human approval (gate 6, L3) — product owner, 2026-10-01
- Design approved: section 6 plus security controls C-1..C-20 (section 5); where section 5 amends section 6, section 5 wins.
- D1 (durable explicit entry point), D2 (rollback at view boundary), D3 (closed `check_principal`), D4 (registry RLS ENABLE without FORCE + column grants) approved with the attached controls.
- RR-1 (timing difference between 404 causes) accepted → `docs/risks.md` R29.
- `template1` PUBLIC revoke approved (local/CI bootstrap; asserted by `make db-check`).

## 6. Design
### 6.1 App layout (`backend/rms/tenancy/`, AUTO)
`apps.py` · `domain/errors.py` (`TenantContextMissing`, `TenantContextActive`) · `data/models.py` (`Restaurant`, `TenantOwnedModel`, managers) · `data/context.py` (the **only** `set_config` caller at runtime) · `data/rls.py` (migration ops) · `services/resolution.py` · `api/views.py` (`TenantAPIView`) · `migrations/` · `tests/` (incl. `probe/` test app, `harness.py`, `catalog.py`, factories). No `urls.py` in 0004.

### 6.2 Registry (`tenancy_restaurant`, platform-level)
- Columns: `id uuid PK`; `name varchar(200) NOT NULL CHECK (btrim(name) <> '')` (OQ1); `status varchar(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','closed'))` via `CheckConstraint`; `created_at`, `updated_at timestamptz`. No transition commands in 0004 (operator console is out of scope).
- Grants (in `tenancy/0001`, after `CreateModel`): `REVOKE ALL ON tenancy_restaurant FROM <app>` (it undoes the default privileges), then `GRANT SELECT (id, name, status) TO <app>`. RLS: `ENABLE` (D4) + policy `restaurant_tenant_read FOR SELECT USING (id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)`.
- ORM: `Restaurant.objects` and the base manager use a queryset with `.only("id","name","status")`, so app-role reads and `tenant` FK traversal never select an ungranted column. Writes exist only on the migrator alias (fixtures, future platform path).

### 6.3 Tenant transaction (C3-2, C3-4)
- `tenant_transaction(tenant_id: uuid.UUID)`, a context manager: `isinstance` check (a raw string is rejected), then `durable` atomic on `default`, then `cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id)])`. It sets `tenant_id_var` and a private `_active_tenant` contextvar, with tokens reset in `finally`.
- `identity_transaction(user_id: uuid.UUID)`: the same for `app.user_id`. It raises `TenantContextActive` if a tenant is active. Unused until 0005.
- `current_tenant_id() -> UUID`: raises `TenantContextMissing` unless `_active_tenant` is set **and** `connections["default"].in_atomic_block`.
- Callers: `TenantAPIView`, tests, and later the job runner. Services never call it; they require it. A source-scan test fails on `set_config` or `app.tenant_id` / `app.user_id` writes outside `data/context.py` and `data/rls.py`.

### 6.4 Tenant-owned base model and manager (C3-9)
- `TenantOwnedModel(models.Model)`, abstract:
  - `id` UUID PK.
  - `tenant = ForeignKey(Restaurant, PROTECT, db_column="tenant_id", editable=False, db_index=False, related_name="+")`.
  - `Meta.constraints = [UniqueConstraint(fields=["tenant","id"], name="%(app_label)s_%(class)s_tenant_id_uniq")]` (parent key for every table; it also serves as the tenant-leading index).
  - `base_manager_name = default_manager_name = "objects"`.
- `objects = TenantManager()`. It is the only manager, with `use_in_migrations = False`. `get_queryset()` calls `current_tenant_id()` (raises outside context) and adds `.filter(tenant_id=…)` (layer 2; RLS is layer 3). Because it is also the base manager, `save()` updates, `refresh_from_db`, related access and delete collection all fail closed without context.
- `save()`:
  - On insert: sets `tenant_id` from context if unset; raises if it is set to another tenant.
  - On update: passes `update_fields` = concrete non-PK fields minus `tenant`, because the app role has no column privilege on `tenant_id`.
- Rules for subclasses: every unique constraint and index leads with `tenant`; tenant→tenant FKs use `db_constraint=False, db_index=False` plus a composite FK op and a `(tenant, x)` index.

### 6.5 Migration ops (`rms.tenancy.data.rls`, REVIEW)
Factory functions returning reversible operations, used in every tenant table's `CreateModel` migration:
- `enable_tenant_rls(table)` → `RunSQL`:
  - forward: `ENABLE` + `FORCE ROW LEVEL SECURITY`; `CREATE POLICY tenant_isolation ON t USING (<expr>) WITH CHECK (<expr>)` (no `TO`, so it also binds the migrator); `<expr>` is the single constant `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid`.
  - reverse: `DROP POLICY`, `NO FORCE`, `DISABLE`.
- `composite_tenant_fk(table, column, parent_table)` → `RunSQL` `ADD/DROP CONSTRAINT <t>_<col>_tenant_fk FOREIGN KEY (tenant_id, col) REFERENCES parent (tenant_id, id) ON DELETE RESTRICT`.
- `restrict_tenant_key_update(table, updatable_columns)` → `RunPython` (forward and reverse):
  - forward: `REVOKE UPDATE ON t FROM <app>; GRANT UPDATE (<cols>) ON t TO <app>`; reverse restores table-level UPDATE.
  - The role name comes from `settings.RMS_DB_APP_ROLE` (= `DB_APP_USER`), is checked against the bootstrap regex and composed with `psycopg.sql.Identifier`.
  - A later column addition calls `grant_update_columns`, and fails closed (permission denied) until it does.
- Static SQL takes table names from `Model._meta.db_table` constants, never from input.
- `for_each_tenant(apps, schema_editor, fn)` (C3-6, data migrations):
  - reads registry IDs on the migration connection (visible: owner, D4);
  - per tenant: `set_config('app.tenant_id', id, true)`, then `fn(tenant_id)` with historical models plus an explicit tenant filter (RLS still forced);
  - clears the setting at the end. Documented in `conventions/backend.md` and tested on the probe table.

### 6.6 Resolution and `TenantAPIView` (C6-1/C6-2, TM-08)
- Route shape `api/v1/r/<uuid:tenant_id>/…`. Django's `uuid` converter accepts canonical lower-case only. Malformed and upper-case values therefore fall to `handler404`, which already returns the `not_found` envelope.
- `TenantAPIView(APIView).dispatch`: `with tenant_transaction(kwargs["tenant_id"]):` → `super().dispatch` → rollback if status ≥ 400 → `response.render()`.
- `initial()` order: `perform_authentication` (401 first; empty until 0005) → `resolve_active_tenant(tenant_id)` → `check_principal` → `check_permissions` → `check_throttles`.
- `resolve_active_tenant`: one `values("id","status")` query under the tenant context. Absent or not `active` raises `NotFound`.
- `check_principal`: raises `NotFound` by default (D3).
- Every failure is the same `404 not_found` envelope before any tenant-table access; the transaction rolls back.
- The device-binding 409 check (pre-transaction) is 0006's; not built.
- Route-scan additions (`test_routes.py`): every route containing `<tenant_id>` must be a `TenantAPIView` subclass; `config.urls` has none in 0004; the `check_principal` override rule (D3c).

### 6.7 Roles and bootstrap (REVIEW, data-engineer)
- `bootstrap.sh` step 4: `REVOKE ALL ON DATABASE postgres FROM PUBLIC; GRANT CONNECT ON DATABASE postgres TO <mig>`. Django's test-DB creation connects the migrator to `postgres`; the app role needs no access. `db-check.sh` already snapshots `datacl`, so idempotency stays covered.
- `core/0001_lock_down_migrations` (RunPython, role-composed as in 6.5): `REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON django_migrations FROM <app>`. SELECT stays, for `runserver`'s migration check. The table does not exist at bootstrap time, so this cannot live there. `tenancy/0001` depends on it.
- No new role. Scheduler deferred (D7). Production migration-job settings: Phase 10 (OQ2).

### 6.8 Test harness (C3-7, SC-29)
- Probe app `rms.tenancy.tests.probe` (label `tenancy_probe`, test settings only):
  - `ProbeParent(TenantOwnedModel)` with `code` and `UniqueConstraint(tenant, code)` (TM-17);
  - `ProbeChild(TenantOwnedModel)` with `parent` (composite FK);
  - its migrations use the 6.5 ops; the test views are under its `urls.py` (`@pytest.mark.urls`).
- **SC-29, verified mechanism.** Mirrors get neither the TestCase atomic nor the flush (3, evidence). So:
  - `harness.ISOLATION_DB = pytest.mark.django_db(transaction=True, databases=["default","migrator"])`. The flush runs on `migrator` (owner; TRUNCATE is not subject to RLS).
  - An autouse guard fails any `transaction=True` test that omits `migrator`.
  - The `two_tenants` fixture asserts that the registry is empty (via migrator) before it creates A and B. Every tenant row needs a registry row (FK) and only the migrator can create one, so an empty registry proves no leftover tenant row.
  - Proof test: test 1 commits rows; test 2 (same module, runs next) sees an empty registry.
- Factories (factory_boy, dev group, `REVIEW` new dependency): `RestaurantFactory` (`database="migrator"`), `ProbeParentFactory`, `ProbeChildFactory` (called inside `tenant_transaction`).
- Required tests:
  - RLS without context: 0 rows, and INSERT rejected by `WITH CHECK`.
  - A context: B's rows unreadable, and UPDATE/DELETE on them affect 0 rows.
  - Manager outside context raises.
  - Cross-tenant composite FK insert raises `IntegrityError`.
  - Same `code` in A and B succeeds.
  - App-role UPDATE of `tenant_id` raises `InsufficientPrivilege`.
  - C3-2: after a committed A block on the same `default` connection, `current_setting('app.tenant_id', true)` is `''`/NULL and a raw count returns 0.
  - Nested and raw-string `tenant_transaction` raise.
  - NT-08: malformed, upper-case, unknown, suspended, closed and closed-hook paths give identical status and body (minus `request_id`).
  - A tenant view that writes then raises `ValidationError` leaves no row (the carried "real row-write rollback test").
  - `for_each_tenant` touches each tenant only under its own context.
  - Registry: app role cannot INSERT/UPDATE or read `created_at`.

### 6.9 Catalog check (C3-5, TM-28; `tenancy/tests/catalog.py` + `test_catalog.py`, in `make test-backend`)
`catalog_failures(alias) -> list[str]`, queried on `default` against the fully migrated test DB (real + probe migrations):
1. Every `public` relation (`relkind r,p`) is either tenant (has a `tenant_id` attribute) or on the platform allow-list `{django_migrations, tenancy_restaurant}`. Anything else fails, which forces a review.
2. Tenant tables: `relrowsecurity AND relforcerowsecurity`. `pg_policies` holds exactly one policy, `tenant_isolation`, with `cmd ALL`, `roles {public}`, and `qual = with_check =` the canonical deparsed expression (captured from the probe table and pinned as a literal). Any other policy must be on an allow-list (registry policy only).
3. `has_column_privilege(app, t, 'tenant_id', 'UPDATE')` is false. No `TRUNCATE`/`REFERENCES`/`TRIGGER` for the app on any table.
4. Every unique constraint and unique index except the PK leads with `tenant_id` (`pg_index.indkey[0]`).
5. Every FK between tenant tables contains `tenant_id` on both sides (`conkey`/`confkey`). A model-introspection test checks that each tenant→tenant ORM FK is covered.
6. App role: not superuser or `BYPASSRLS`; `pg_has_role(current_user, r.oid, 'MEMBER')` for no other role (transitive); owns nothing; `rolconfig` includes both timeouts.
7. Views without `security_invoker=true` in `reloptions`: none. Materialized views in `public`: none.
8. `SECURITY DEFINER` functions outside `pg_catalog`/`information_schema` equal the allow-list `{(signature, md5(prosrc))}`, which is empty in 0004.
9. Non-superuser roles with `rolbypassrls`: allow-list empty.
10. Registry: app has SELECT only on `id, name, status` and no table DML. `django_migrations`: no INSERT/UPDATE/DELETE/TRUNCATE.

Negative tests of the checker (migrator, transactional, cleaned up by the flush):
- a `tenant_id` table without `FORCE` is reported;
- a non-`security_invoker` view is reported;
- a unique constraint not leading with `tenant_id` is reported.

### 6.10 CI and Make (REVIEW)
- `migrations-check` also runs with `--settings=config.settings.test` (probe app).
- New target `migrations-roundtrip`: `migrate` → `migrate tenancy_probe zero`… → reverse the real apps to `zero` → `migrate` again, on the dev DB as migrator. It runs as a CI backend step after `db-check` and proves every RLS op is reversible.
- No new job, action or secret.

### 6.11 Open questions
- **OQ1 (non-blocking):** the maximum length and allowed characters of a restaurant name. TM-30 requires a limit; 200 is a technical placeholder until the operator-console change confirms it with the product owner.
- **OQ2 (non-blocking):** the shape of the production migration-job settings and how it gets `DB_APP_USER` (name only). Phase 10.

## 7. Implementation (gate 7)
*(backend-engineer, 2026-10-02. Two sessions: a previous implementer, stopped part-way, and this one. Nothing is committed; branch `feat/0004-tenancy-rls`.)*

### 7.1 Who did what
**Previous implementer.** Its work was found uncommitted in the tree, read in full and verified against §6 + C-1..C-20. It was kept, not rewritten. Built:
- the `tenancy` app (§6.1): registry model and migration (§6.2, D4); `tenant_transaction` / `identity_transaction` (C-1(a)–(g)); `TenantOwnedModel` / `TenantManager` / `TenantQuerySet` (C-7, C-10); migration ops and `for_each_tenant` (§6.5, C-11, C-15); `resolve_active_tenant` and `TenantAPIView` (§6.6, D1–D3, C-4, C-5, C-6);
- `core/0001_lock_down_migrations` (§6.7);
- the probe app, harness, factories and catalog check (§6.8, §6.9, C-12, C-13, C-14, C-20);
- the test modules `test_catalog`, `test_context`, `test_harness`, `test_manager`, `test_migrations`, `test_models`, `test_rls`, `test_scans`, `test_views`, plus `config/tests/test_settings_db.py` (C-18) and the tenant-route rules in `test_routes.py` (C-5(c));
- settings (`INSTALLED_APPS`, `RMS_DB_APP_ROLE`, probe app in test settings only), `conftest.py` (SC-29 guard, `serialized_aliases=[]`), factory_boy in the dev group, `docs/risks.md` R29.

State on pickup: `make lint-backend typecheck-backend` clean; `make test-backend` **463 passed**.

**This session.**
1. **Fix, C-1(c).** `TenantAPIView.dispatch` reset its log-context token (`tenant_id_var`) *after* the atomic block, so an `on_commit` callback registered by a view still saw the tenant in log context. The reset now runs in a `finally` inside the block. Regression test `test_views.py::test_on_commit_after_a_tenant_view_runs_without_context` (new probe outcome `on-commit`). It failed against the old code (`log_tenant_id` was the tenant UUID) and passes now.
2. **C-12(12).** `read_only_catalog_failures()` (own `durable` transaction, `SET TRANSACTION READ ONLY` first) and `main()` for `python -m rms.tenancy.tests.catalog`. Added `make catalog-check` and a CI step after `make migrate`. Test `test_catalog.py::test_read_only_entry_point_is_clean_and_read_only` (asserts `transaction_read_only = on` inside the real call).
3. **C-17 / §6.10.** `config/tests/roundtrip.py` plus `make migrations-roundtrip` on a throwaway DB `rms_roundtrip`:
   - the name guard refuses anything not matching `^rms_roundtrip(_[a-z0-9]{1,20})?$`, and refuses `DB_NAME`, the test DB and the template;
   - both aliases are re-pointed before the first connection, and this is checked before the first query;
   - the migrator creates the DB from `rms_template`, does `REVOKE ALL … FROM PUBLIC`, and grants CONNECT to the app role and the migrator;
   - the run applies everything, runs the catalog check, reverses `tenancy_probe` → `tenancy` → `rms_core` to zero, asserts no relation, policy or history row is left (except `django_migrations`), migrates again and runs the catalog check;
   - the DB is dropped in `finally`.

   Guard tests are in `config/tests/test_roundtrip.py`. `make migrations-check` also runs with `--settings=config.settings.test`. CI and `make check` got the new steps.
4. **C-19.**
   - `bootstrap.sh` step 5: `REVOKE ALL ON DATABASE postgres FROM PUBLIC; GRANT CONNECT ON DATABASE postgres TO <mig>; REVOKE ALL ON DATABASE template1 FROM PUBLIC`.
   - `db-check.sh` assertion 4 fails on any of: a PUBLIC entry or a NULL ACL on `postgres`/`template1`; app-role CONNECT or TEMP on either; either DB missing.
   - Seen failing on the un-bootstrapped container (5 problem lines), then passing.
5. **Docs** (§3 "Docs to update"):
   - `tenancy.md`: an "As built" table plus Built/Planned marks;
   - `conventions/backend.md`: new "Tenant plane" section (views, models, migrations), "Tests" harness rules, factory_boy;
   - `testing-strategy.md`: isolation suite, catalog check, scans and factories marked Built; CI row;
   - `data.md`: table register (registry, `django_migrations`, test-only probe tables) and the C-16/D8 key rule;
   - `operations.md`: new targets, bootstrap step 5, db-check 4, CI order, a bind-mount note;
   - `README.md` and `CHANGELOG.md`.
6. This section.

### 7.2 Files changed (whole change, both sessions)
- **New:** `backend/rms/tenancy/**` (app, migrations, tests, probe app), `backend/rms/core/migrations/{__init__,0001_lock_down_migrations}.py`, `backend/config/tests/{test_settings_db,roundtrip,test_roundtrip}.py`, this record.
- **Modified (backend):** `config/settings/{base,test}.py`, `config/tests/{test_routes,test_validation}.py`, `conftest.py`, `pyproject.toml`, `uv.lock`.
- **Modified (infra):** `Makefile`, `.github/workflows/ci.yml`, `scripts/db/bootstrap.sh`, `scripts/ci/db-check.sh`.
- **Modified (docs):** `docs/architecture/{tenancy,data}.md`, `docs/conventions/backend.md`, `docs/process/{testing-strategy,operations}.md`, `docs/risks.md` (R29), `README.md`, `CHANGELOG.md`.
- **Not touched:** `frontend/`, `config/urls.py` (no tenant route), the 0003 error handler, `DenyAll`/`PUBLIC_ROUTES`, production settings, the permission catalog, ADR texts, `.claude/`, `CLAUDE.md`.

### 7.3 Decisions
**This session.**
- AUTO: the C-1(c) fix; the catalog entry point inside `rms/tenancy/tests/catalog.py` (its §6.9 home), run with `python -m`; doc wording.
- REVIEW (data-engineer):
  - the round-trip runner connects with psycopg directly to the `postgres` maintenance DB as the migrator;
  - it runs `DROP DATABASE IF EXISTS` on a leftover `rms_roundtrip`, only after the name guard;
  - the name pattern itself.
- REVIEW: CI now runs `make migrate` on its per-run dev DB, which `catalog-check` needs (C-12(12)).
- REVIEW: `make check` includes `migrations-roundtrip` but not `catalog-check`, which needs a migrated dev DB. The same check runs in the tests and in the round trip.
- REVIEW: the C-19 grant keeps the migrator's CONNECT on `postgres` (Django's `_nodb` connection for test and round-trip DB creation).

**Previous implementer.** Choices beyond the letter of §6, recorded for gate 8/9:
- REVIEW: extra domain error `TenantMismatch`, raised by writes or deletes that name another tenant.
- REVIEW: `TenantOwnedModel.delete()` also checks the tenant.
- REVIEW: `tenant_transaction(..., bind_log_context=False)` implements C-1(g).
- REVIEW: the ops are `Operation` subclasses (`RestrictTenantKeyUpdate`, `GrantUpdateColumns`, `RestrictToColumnRead`, `EnableRegistryRLS`, `LockDownMigrationTable`, `EnableTenantRLS`, `CompositeTenantFK`) behind the §6.5 factory functions.
- REVIEW: **`core/0001` imports `rms.tenancy.data.rls.LockDownMigrationTable`**, so `rms.core` migrations now depend on `rms.tenancy` code. The class docstring explains why (the checked role name). The architect should confirm this direction or move the role helper into `rms.core`.
- REVIEW: `LockDownMigrationTable` also revokes app-role privileges on the `django_migrations` ID sequence (beyond §6.7). The catalog check additionally forbids app-role privileges on any sequence.
- REVIEW: `conftest.py` sets `serialized_aliases=[]`, so `serialized_rollback` is unavailable (documented).
- REVIEW: mypy overrides for the untyped `factory` package, and a ruff `RUF012` ignore for `**/migrations/*.py`.
- REVIEW (applied by the earlier gate-5 review): extra catalog rules (sequence privileges, identity/generated columns, registry policy count) and extra negative cases (29 planted cases, more than the 17 C-13 requires).

**APPROVAL.** None new. Applied as approved: `template1` PUBLIC revoke (local/CI bootstrap, asserted by `make db-check`).

### 7.4 Traceability
| Item | Tests |
|---|---|
| Crit. 1, D4, N-13 | `test_rls.py::test_registry_as_the_app_role`, `test_registry_constraints`; catalog rule 10 + negatives |
| Crit. 2, C-1, N-04, N-05 | `test_context.py` (nesting and plane mixing, non-UUID args before SQL, autocommit/atomic preconditions, C3-2 for both planes with positive control, rollback, `on_commit`, thread, TestCase-mode clear, planted leaks); `test_views.py::test_on_commit_after_a_tenant_view_runs_without_context` |
| Crit. 3, C-7, C-8, C-10, N-06, N-10 | `test_manager.py` (22 access paths outside context, A vs B, key immutability, `select_related("tenant")` fails closed); `test_models.py` (introspection + self-test) |
| Crit. 4, 10, C-11, C-15, N-10, N-11 | `test_migrations.py` (role checks incl. unset/unknown/superuser/migrator, op round trip and C-11(c) post-check, `for_each_tenant`, migration-graph rule) |
| Crit. 5, N-08, N-09, N-12 | `test_rls.py` (no context, A vs B, composite FK insert and update via ORM and raw SQL, per-tenant uniqueness, key-column UPDATE denied, `django_migrations` writes denied) |
| Crit. 6, C-4, C-5, C-6, N-01, N-02, N-15 | `test_views.py` (group R byte/header/query identity × 3 methods, group M × 5 malformed × 3 methods, closed hook, rollback matrix for 400/403/404/409/500/swallowed DB error/streaming, duplicate without constraint leak); `test_routes.py` tenant-route rules and self-test; `test_scans.py` override checks |
| Crit. 7, C-12, C-13, N-07 | `test_catalog.py` (clean as app role and as migrator, non-vacuous, 29 planted violations each followed by a no-residue check, definer `proconfig` change, zero-tenant mode, read-only entry point) |
| Crit. 8 (SC-29, `django_migrations`, row-write rollback, `postgres` revoke), C-20, N-14 | `test_harness.py` (guard × 14 cases, proof pair, session guards); `test_rls.py` N-12; `test_views.py::test_failure_after_a_write_leaves_no_row`; `make db-check` |
| Crit. 9 | `rms/tenancy/tests/{harness,factories}.py`, used by every tenant test |
| Crit. 11 | Docs in 7.1 item 5 |
| C-3, C-9, N-03, N-16 | `test_scans.py` (scans + self-tests); `test_settings_db.py` |
| C-17 | `test_migrations.py::test_migration_graph_keeps_tenant_tables_with_their_rls`; `config/tests/test_roundtrip.py`; `make migrations-roundtrip` |
| C-18 | `config/tests/test_settings_db.py` |
| C-19 | `make db-check` (assertion 4) |

### 7.5 Verification (this session, 2026-10-02, local `postgres:16` container)
| Command | Result |
|---|---|
| `make lint` | exit 0: ruff check and format (78 files) clean; ESLint and Prettier clean; `lint-shell` skipped by the Makefile (shellcheck not installed locally) |
| shellcheck v0.10.0 (container, `--network none`) on all 5 scripts | exit 0, no findings (stand-in for the skipped `lint-shell`; CI runs it with `REQUIRE_SHELLCHECK=1`) |
| `make typecheck` | exit 0: mypy strict, no issues in 78 files; `tsc -b --noEmit` clean |
| `make test-backend` | **481 passed**, 0 failed, 0 skipped (463 on pickup + 18 new) |
| `make migrations-check` | "No changes detected" with local and with test settings |
| `make db-check` | all 4 assertions pass (loopback port; wrong password rejected; bootstrap re-run idempotent; `postgres`/`template1` grant nothing to PUBLIC or the app role) |
| `make migrations-roundtrip` | create `rms_roundtrip` → apply 3 migrations → reverse `tenancy_probe`, `tenancy`, `rms_core` to zero → apply again → catalog check clean → dropped; afterwards `pg_database` lists only `postgres, rms, rms_template, template0, template1` |
| `make catalog-check` | not green locally, as expected: the dev DB is unmigrated and must stay so. It reported only `10: platform table django_migrations is missing` and `10: … tenancy_restaurant is missing`; every role, ACL and default-privilege rule passed. CI runs it after `make migrate`. The no-tenant-table mode is covered by `test_zero_tenant_tables_fail_unless_allowed` |
| `make workflow-lint` | exit 0: zizmor "No findings"; `check-workflows: OK (1)`; `test-check-workflows: OK (26 fixtures rejected as expected)` |
| `make audit` | exit 0: pip-audit "No known vulnerabilities found"; npm audit 0 vulnerabilities (both runs) |
| `make check` | exit 0: lint, typecheck, migrations-check, migrations-roundtrip, tests (481 backend, 73 frontend), deploy-check, audit, secrets (no leaks), build, secrets-dist (no leaks), workflow-lint |
| Secret grep of all uncommitted changes (private-key headers, provider key prefixes, URL credentials, password literals) | no hits |

Environment actions:
- `make up` (the container was stopped).
- `make down` + `make up` to recreate the container, so the single-file bind mount of `bootstrap.sh` shows the edited file (verified: the old inode had no `template1`). The `rms_db-data` volume was kept.
- `make db-bootstrap` applied step 5 locally.

Not done: no `make migrate`/`make setup` on the dev DB, no DB or volume dropped or recreated, no commit. The dev DB still has 0 relations in `public`.

### 7.6 Open items and handover
- **Non-blocking, 0005:** `check_principal` is `@final` (C-5(a)), so `rms.access.api.MemberTenantAPIView` will need a reviewed `# type: ignore[misc]`, as the probe's test view uses, or a design note. Add `rms.access.api` to `ALLOWED_OVERRIDES` (`test_scans.py`). The membership lookup must run the same queries for active and inactive tenants (C-6 handover).
- **Non-blocking:** `template0` keeps `=c/postgres` (PUBLIC CONNECT), but `datallowconn` is false, so it cannot be connected to. Out of C-19 scope.
- **REVIEW for the architect:** the `core/0001` → `rms.tenancy` import direction (7.3).
- Residual risks unchanged: RR-1 (R29), RR-2 (R16), RR-3 (R1 open until Phase 10), RR-4, RR-5.

## 8. Testing (gate 8)
*(qa-engineer, 2026-10-02. Read every test module listed in 7.4 against §2, §5 and §6, then ran mutation checks on the production code. Test-only changes; no production file was changed. Nothing is committed.)*

### 8.1 Verdict on the existing suite
The suite proves what 7.4 claims, with three gaps (G1–G3) and one weak assertion (W1). Each is now covered by a new test. The known vacuity traps were checked:
- **F4 (migrator reads under FORCE):** no "no row" or "B unchanged" assertion reads a tenant table through the migrator without context. All of them use `rows_visible_to` or the scoped manager under a context. `test_rls.py::test_migrator_without_context_reads_nothing_under_force` pins the trap itself. The proof pair's empty-registry check reads the registry, which is not forced (D4), so it is non-vacuous.
- **F1 (savepoint leak):** every context-sensitive test is `ISOLATION_DB`. The TestCase-mode tests assert `in_atomic_block`, and mutation M03 shows the C-1(d) clear is what they prove.
- **SC-29 (mirror not flushed):** `two_tenants` asserts an empty registry through the owner, and the proof pair runs in order (`-rA`: both PASSED, proof 2 not skipped). The C-20(a) guard is unit-tested on 14 item shapes. Every transactional test in the tree declares `migrator`; otherwise the autouse guard would fail it.
- **Positive controls:** every 0-row assertion in `test_rls`, `test_manager`, `test_views`, `test_context` and `test_harness` has a matching count > 0 in the same test, or a same-tenant control.

Gaps and weak assertion (all fixed with tests, none is a production defect):
- **G1, layer 2 not isolated.** No test showed that `TenantManager` adds `tenant_id = <context>` on its own. RLS hid it: mutation M11 (the filter removed) failed **no** existing test.
- **G2, C-1(g) untested.** T4-24 had no test (§5.3 "—"). Mutation M13 (log context bound before resolution) failed no existing test.
- **G3, no concurrency test** for the race §5.3 names: A and B open at the same time.
- **W1, the `tenant_id` case of `test_app_role_cannot_update_key_columns`** passes even with table-level UPDATE granted back (mutation M19). `SET tenant_id = <B>` is refused by the policy's WITH CHECK, with the same SQLSTATE 42501, not by the missing column grant. The existing test is kept unchanged (it is still a true statement). The new test isolates the grant.

### 8.2 Tests added (23, test-only)
| File | Test | Proves |
|---|---|---|
| `rms/tenancy/tests/test_context.py` | `test_commit_clears_the_setting_even_without_the_exit_clear` | C3-2 independent of C-1(d): the setting is transaction-local, so the commit resets it with the clear disabled |
| | `test_concurrent_tenant_transactions_stay_isolated` | G3: two threads, A and B open at the same time (barrier). Each sees only its own context, setting and rows, on two backends |
| | `test_planted_session_level_leak_on_a_reused_connection_makes_entry_raise` | R13 in the production shape: a session-level `app.tenant_id` on a reused connection makes entry raise. Positive control: the leak would expose B. The connection is closed in `finally` |
| `rms/tenancy/tests/test_manager.py` | `test_manager_filter_holds_when_rls_would_allow_the_row` | G1: app context A, migrator connection under B's RLS context (shows B, positive control). `using`/`db_manager` still return nothing |
| | `test_create_paths_naming_b_raise_in_the_app` ×3 | `create`, `get_or_create`, `update_or_create` naming B raise `TenantMismatch`; A and B unchanged |
| | `test_update_or_create_cannot_move_a_row_to_b` | Moving an existing row to B raises before any SQL |
| `rms/tenancy/tests/test_views.py` | `test_write_view_rejects_every_non_active_tenant_before_writing` ×3 | Unknown, suspended and closed tenants get 404 on the open-hook view, with no row written; an active control gives 201. The closed-hook group R test cannot show this |
| | `test_tenant_comes_only_from_the_path` | C-5(d): B in the body, the query string and `X-Tenant-ID`/`X-Restaurant-ID` is ignored; the row lands in path tenant A |
| | `test_log_context_is_bound_only_after_resolution` | G2, C-1(g)/T4-24: `tenant_id_var` is `None` during resolution for unknown, suspended and active tenants; set in the handler only for active (control); `None` after |
| `rms/tenancy/tests/test_rls.py` | `test_key_column_grant_denies_even_a_same_value_rewrite` ×3 | W1: `tenant_id = tenant_id`, `tenant_id = <A>` and `id = id` are denied with "permission denied for table" (the grant, not the policy). Control: `code = code` updates 1 row |
| `rms/tenancy/tests/test_catalog.py` | `test_role_rules_flag_privileged_roles` | C-12(6) had no negative test: the migrator cannot create or alter roles, so no DDL can be planted. Checked instead with `postgres` and the migrator in the app role's place (SUPERUSER, BYPASSRLS, `pg_read_all_data`/`pg_write_all_data` membership, ownership, missing timeouts, CREATEDB, schema CREATE, TEMP, registry table grant). Control: the real role is clean |
| | `test_no_role_can_persist_a_context_setting` ×6 | T4-04: neither the app role nor the migrator (DB owner) can run `ALTER ROLE … SET app.*`, `ALTER ROLE … IN DATABASE … SET app.*` or `ALTER DATABASE … SET app.*`; PG16 raises `InsufficientPrivilege`. The session-level form is possible, which is why C-1(b) exists (covered above) |

Strings that would match the C-3 scan are built by concatenation, as `test_scans.py` does. The scan flagged my first draft, which confirms it covers test files.

### 8.3 Mutation checks
Each mutation was a single exact edit to a production (or checker) file. The full suite was run, and the file was restored from a byte copy and verified by SHA-256. All six touched files match their pre-mutation checksums, and none of them shows in `git status` beyond the untracked state it already had.

| # | Mutation | Result (full suite) | Caught by |
|---|---|---|---|
| M01 | `EnableTenantRLS`: `FORCE` → `NO FORCE` | 44 failed | catalog (clean, as migrator, every planted case), `test_migrator_without_context_reads_nothing_under_force`, `test_for_each_tenant_scopes_each_call`, op round trip, new layer-2 test |
| M02 | `CompositeTenantFK` forward → `SELECT 1` | 5 failed | `test_cross_tenant_child_insert/update_fails_at_the_db`, `test_parent_with_children_cannot_be_deleted`, `test_every_tenant_fk_has_its_composite_constraint`, op round trip |
| M03 | C-1(d) exit clear → `SELECT 1` | 1 failed | `test_setting_is_cleared_after_exit_in_test_case_mode` (as expected: in commit mode the commit resets it) |
| M04 | entry `set_config(…, true)` → session-level | 23 failed + 51 errors | `test_reused_connection_carries_no_tenant_context` (C3-2), new commit-clear test, and every later test via leak detection |
| M05 | C-1(b) leak detection off | 3 failed | both planted-leak tests and the new session-level leak test |
| M06 | no `set_rollback` on status ≥ 400 | 7 failed | rollback matrix 400/403/404/409, group R ×3 (its SQL trace must end in `ROLLBACK`) |
| M07 | C-4(b) `needs_rollback` check off | 1 failed | `[swallow-500]` |
| M08 | C-4(c) streaming check off | 1 failed | `[stream-500]` |
| M09 | `check_principal` opened (returns None) | 4 failed | `test_default_hook_gives_404_for_an_active_tenant`, group R ×3 |
| M10 | resolution accepts non-active tenants | 4 failed | existing suspended write test, new closed/suspended cases, log-context test |
| M11 | `TenantManager` without the tenant filter | 1 failed | **only** the new layer-2 test (G1) |
| M12 | registry `ENABLE ROW LEVEL SECURITY` removed | 42 failed | `test_registry_as_the_app_role`, catalog |
| M13 | `TenantAPIView` binds the log context before resolution | 1 failed | **only** the new log-context test (G2) |
| M14 | C-1(e) atomic-identity check off | 1 failed | `test_copied_context_in_another_thread_has_no_tenant` |
| M15 | `type(x) is UUID` → `isinstance` | 2 failed | UUID-subclass cases |
| M16 | `bulk_create` without the tenant claim | 1 failed | `test_bulk_create_naming_b_raises_in_the_app` |
| M17 | catalog ignores missing FORCE | 1 failed | planted "tenant table without FORCE" |
| M18 | contextvar reset moved after the atomic block (the pre-fix C-1(c) bug) | 47 failed + 51 errors | `on_commit` tests, `test_logging`, every later test |
| M19 | table-level UPDATE granted back after the restrict op | 42 → 45 failed | catalog, `test_restrict_tenant_key_update_round_trip_and_post_check`, existing `[id]` case; `tenant_id` only by the new grant test (W1) |

Not mutated: the SC-29 flush itself (Django internals; covered by the proof pair plus the guard self-tests) and `LockDownMigrationTable` (its own post-check aborts test-DB setup, so it fails loudly; N-12 asserts all four writes).

### 8.4 Traceability: acceptance criteria
| Crit. | Tests / checks |
|---|---|
| 1 Registry, CHECK, column grants, no app status change | `test_rls.py::test_registry_as_the_app_role`, `::test_registry_constraints`; catalog rule 10 + planted "registry FORCE / column grant widened / table-level grant"; M12 |
| 2 Single entry point, bound UUID, transaction-local; identity plane | `test_context.py` (all 30); `test_scans.py::test_only_the_entry_point_writes_context_settings` + self-tests; new `test_no_role_can_persist_a_context_setting`; M03–M05, M14, M15 |
| 3 Scoped base model/manager, raises without context, no unscoped manager | `test_manager.py` (22 outside-context paths, A vs B, keys, new layer-2 and create-path tests); `test_models.py`; M11, M16 |
| 4 Migration pattern (ENABLE+FORCE, pinned expression, `UNIQUE(tenant_id,id)`, tenant-leading indexes, no key UPDATE) | `test_migrations.py` (op round trips, C-11 checks, graph rule); catalog rules 2/4/5/11; `test_rls.py` key-column tests + new grant test; M01, M02, M19 |
| 5 Probe table: no context → 0 / writes rejected; A vs B; composite FK; C3-2 | `test_rls.py::test_no_context_reads_nothing_and_cannot_write`, `::test_a_cannot_read_or_write_b`, `::test_cross_tenant_child_insert/update_fails_at_the_db`; `test_context.py::test_reused_connection_carries_no_tenant_context` + new commit-clear and session-leak tests; M02, M04 |
| 6 Path resolution, uniform 404 before tenant data, hook closed | `test_views.py` group R/M, default hook, new non-active write matrix, tenant-from-path test; `test_routes.py` tenant rules; `test_scans.py` override checks; M09, M10 |
| 7 CI catalog check | `test_catalog.py` (clean ×2, non-vacuous, 29 planted, definer config, zero-tenant mode, read-only entry point, new role-rule negatives); `make migrations-roundtrip` (catalog after each forward); CI step `make catalog-check` (not run locally, see 8.6); M17 |
| 8 SC-29; `django_migrations` lock-down; row-write rollback; `postgres` revoke | `test_harness.py` (guard ×14, proof pair, session guards); `test_rls.py::test_app_role_cannot_write_django_migrations` ×4; `test_views.py::test_failure_after_a_write_leaves_no_row` ×7; `make db-check` assertion 4 |
| 9 Two-tenant fixtures/factories | `harness.py` (`two_tenants`, `rows_visible_to`, `ISOLATION_DB`), `factories.py`; used by every tenant test |
| 10 Migrator-only migrations; per-tenant data-migration pattern | catalog rule 3 (app has no CREATE on schema or DB) + rule 6; `test_migrations.py::test_for_each_tenant_*`, `::test_migration_tenant_context_*`; documented in `conventions/backend.md` "Tenant plane" |
| 11 Docs | Checked: `tenancy.md` (Built marks), `conventions/backend.md` "Tenant plane", `testing-strategy.md` isolation suite Built. Drift found: see 8.7 F-1 |

### 8.5 Traceability: controls and required negatives
| Control | Test / check |
|---|---|
| C-1 (a)–(g) | (a) `test_non_uuid_arguments_raise_before_any_sql` ×10, `test_entry_inside_a_non_test_atomic_raises`, `test_entry_with_autocommit_off_raises`; (b) planted-leak ×3; (c) `on_commit` ×2; (d) TestCase-mode clear; (e) thread test; (f) nesting ×5, planted cross-plane; (g) new log-context test |
| C-2 | Every context test is `ISOLATION_DB`; `test_two_tenants_refuses_a_test_transaction` |
| C-3 | `test_scans.py` scan + 8 self-tests + reads ignored |
| C-4 (a)–(d) | rollback matrix ×7 (incl. swallow, stream, crash); M06–M08 |
| C-5 (a)–(d) | `@final` + mypy strict (`make typecheck` clean); override test + 2 self-tests; route rules + self-test; zero tenant routes in `config.urls`; new tenant-from-path test |
| C-6 | group R ×3 methods (status, bytes, headers, query count, SQL trace); group M 5×3 |
| C-7 (a)–(d) | `test_raw_and_extra_raise_under_context`, bulk_create/bulk_update/update/save key tests, new create-path tests |
| C-8 | `test_models.py` ×4 incl. self-test |
| C-9 (a)(b) | `test_scans.py` raw-SQL and migrator/factory scans + self-tests |
| C-10 | `test_select_related_tenant_fails_closed`, `test_tenant_fk_traversal_selects_only_granted_columns` |
| C-11 (a)–(e) | `test_checked_app_role_refuses` ×7, `_accepts_`, `test_restrict_tenant_key_update_round_trip_and_post_check`, `test_key_fields_can_never_be_made_updatable` ×4, `test_operations_refuse_bad_names` ×5, `test_unset_app_user_refuses_to_start` ×2 |
| C-12 (1)–(12) | `test_catalog.py` (all); rule 6 now also negative-tested (new) |
| C-13 | 29 planted cases + definer-config case + no-residue checks (all 17 required cases present) |
| C-14 | Positive controls verified in every 0-row assertion (8.1) |
| C-15 | `test_for_each_tenant_refuses_a_non_atomic_migration`, `_scopes_each_call` (incl. `other_updated == 0`), context guards, clear after error |
| C-16 | Documented (`conventions/backend.md`); no serializer exists in 0004, so not testable yet |
| C-17 | `test_roundtrip.py` ×16; migration-graph test; `make migrations-roundtrip` |
| C-18 | `test_settings_db.py` ×9 |
| C-19 | `make db-check` assertion 4 |
| C-20 (a)–(c) | guard ×14; docstring in `harness.py`; proof pair |

| Neg. | Test |
|---|---|
| N-01 | `test_group_r_is_indistinguishable` ×3, `test_group_m_matches_group_r` ×15 |
| N-02 | override self-tests, `test_tenant_route_scan_flags_bad_routes`, `test_default_hook_gives_404_for_an_active_tenant` |
| N-03 | `test_context_write_scan_self_test` ×8 |
| N-04 | C3-2 ×2 planes, `on_commit`, TestCase clear, planted leaks ×2 (+ new session-level), thread; new concurrency test |
| N-05 | nesting ×5, non-UUID ×10 |
| N-06 | 22 outside-context paths + no-change check; A vs B get/pk__in/update/delete/bulk_create/raw insert/select_related; new create paths and layer 2 |
| N-07 | 29 planted + definer config (+ new role-rule negatives) |
| N-08 | composite FK insert and update, ORM and raw |
| N-09 | `test_same_code_in_both_tenants_and_duplicate_in_one`, `test_duplicate_code_response_reveals_no_constraint` |
| N-10 | key-column UPDATE ×2 (+ new same-value ×3), app-side key tests, C-11 refusals |
| N-11 | `for_each_tenant` ×2 + context guards ×2 |
| N-12 | `test_app_role_cannot_write_django_migrations` ×4 |
| N-13 | `test_registry_as_the_app_role` |
| N-14 | guard ×14, proof pair, `test_existing_session_guards_still_pass` |
| N-15 | `test_success_commits`, rollback matrix ×7 |
| N-16 | `test_settings_db.py`, migrator scan |

Standard negatives not applicable in 0004: 401 (no authentication until 0005), 403 permission codes (0006), deactivated membership (0005), invalid state transition (no command), replay/idempotency (no state-changing production endpoint, §5.3). Cross-tenant 404 by object ID needs an object endpoint; the first feature endpoint must add it with this harness.

### 8.6 Runs (2026-10-02, local `postgres:16` container)
| Command | Result |
|---|---|
| `make test-backend` (baseline, before additions) | 481 passed |
| `make test-backend` ×3 (after additions) | **504 passed** each run (18.8 s, 19.4 s, 21.3 s); 0 failed, 0 skipped |
| `make test-backend PYTEST_ARGS="-q rms/tenancy/tests/test_context.py -k 'concurrent or thread or session_level'"` ×10 | 3 passed every run; no flakiness seen |
| `make test-backend PYTEST_ARGS="-q -rA rms/tenancy/tests/test_harness.py -k proof"` | proof 1 PASSED, proof 2 PASSED (not skipped) |
| `make lint-backend typecheck-backend` | ruff clean, 78 files formatted; mypy strict "no issues in 78 source files" |
| `make migrations-roundtrip` | create `rms_roundtrip` → apply 3 → reverse `tenancy_probe`, `tenancy`, `rms_core` → apply again → catalog clean → dropped; `pg_database` afterwards: `postgres, rms, rms_template, template0, template1` |
| `make db-check` | exit 0; all 4 assertions pass |
| `make check` | exit 0: lint, typecheck, migrations-check ×2 ("No changes detected"), migrations-roundtrip, tests (504 backend, 73 frontend), deploy-check, audit (0 vulnerabilities), secrets (no leaks), build, secrets-dist, workflow-lint |
| `make catalog-check` | not run: it needs a migrated dev DB, and `make migrate` on the dev DB is out of bounds for this gate. The same check runs inside the test suite and the round trip; CI runs it after `make migrate` |

Dev DB untouched: 0 relations in `public` after all runs. Flaky behaviour: none observed.

### 8.7 Findings for the orchestrator
- **F-1 (low, docs drift, rule 8):** `backend/rms/core/context.py:6` says `tenant_id` "stay[s] `None`", and `docs/conventions/backend.md:106` says it is "reserved for 0004/0005". 0004 now sets it (`TenantAPIView.initial`, `tenant_transaction`). Owner: backend-engineer. Not changed here (test-only gate).
- **F-2 (info):** two controls were proven only by tests added in this gate (M11 layer 2, M13 C-1(g)). Gate 9 should treat those tests as part of the C-1/C-14 evidence.
- **F-3 (info):** the `[tenant_id]` case of `test_app_role_cannot_update_key_columns` is satisfied by WITH CHECK, not by the grant (W1). It is kept, and the grant is now proven by `test_key_column_grant_denies_even_a_same_value_rewrite`. Proposal, not applied: rename the old case's docstring to say so.
- **F-4 (info, handover to 0005):** the session-level `SET app.*` is available to every role (verified). Only C-1(b) and the C-3 scan stop it. A future pooler (Phase 10, `CONN_MAX_AGE` > 0) must keep the new session-leak test green.
