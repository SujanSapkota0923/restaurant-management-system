# Backend Conventions

**Status:** Proposed. The "Django + DRF" section describes the scaffold as built in change 0003 (ADR-0004) and the tenancy foundation built in change 0004. Items marked **Planned** arrive with the change named.

## Stack-agnostic
- Module per bounded context (`domain-model.md`), each with `api`, `services`, `domain`, `data` layers (`overview.md`).
- Handlers: authenticate, resolve tenant, check permission, validate input, call one service, map result. No business rules.
- Services: take the acting membership explicitly, enforce object-level authorization, run in one transaction, emit audit and domain events, raise typed domain errors.
- Domain errors are mapped to the API error envelope in one place.
- Settings from environment variables with validation at startup; the app refuses to start in production with debug on, missing secrets, or wildcard hosts.
- Logging: structured JSON, includes `request_id`, `tenant_id`, `membership_id`; redaction filter for secrets and personal data.
- Background jobs: JSON payloads with `tenant_id`; set tenant context before querying; idempotent; retries with backoff.
- Time: all logic in UTC; business-day boundaries computed with the restaurant timezone.

## Django + DRF (ADR-0004, as built in changes 0003 and 0004)

### Versions and tooling
- Python 3.12 (`backend/.python-version`, `requires-python >=3.12`), managed with **uv**. `backend/uv.lock` is committed. Install with `uv sync --locked`; every `make` target uses `uv run --locked`, so lock drift fails.
- Runtime (locked): Django 5.2.17 (LTS line, `>=5.2,<5.3`), Django REST Framework 3.18.1, psycopg 3.3.6 (`psycopg[binary]`; source build vs. binary wheel for production is decided in Phase 10).
- Dev (locked): pytest 9.1.1, pytest-django 4.14.0, ruff 0.16.9 (exact pin), mypy 1.19.1, django-stubs 5.2.9, djangorestframework-stubs 3.16.9, factory-boy 3.3.3 (0004; pulls in Faker 40.40.0, which the factories do not use). factory_boy has no complete type hints: only `rms/tenancy/tests/factories.py` calls it (mypy override there), and tests use its typed `make_*` functions.
- Deliberately not used: django-environ, structlog, python-json-logger, dj-database-url, django-cors-headers, gunicorn, celery/redis, whitenoise. Adding a dependency needs the design to list it (`REVIEW`).
- **ruff:** line length 100; rules `E,W,F,I,B,UP,S,DJ,SIM,RUF,N`. Tests ignore `S101` (assert) and `S603/S607` (fixed-argv subprocess). Settings modules ignore `F403/F405` (star import of `base`). Any other `noqa` names its rule and a reason.
- **mypy:** `strict = true`, with the django-stubs and DRF-stubs plugins on `config.settings.test`. Runs with the env file loaded (`make typecheck-backend`).
- **pip-audit** 2.10.1 through `uvx`, on the exported lockfile (`make audit-backend`).
- Commands: `make lint-backend`, `make fmt-backend`, `make typecheck-backend`, `make test-backend` (`PYTEST_ARGS=...` passes extra arguments; includes the catalog check), `make migrations-check` (local and test settings), `make migrations-roundtrip` (throwaway DB), `make catalog-check` (migrated dev DB, read-only), `make deploy-check`.

### Layout
- `backend/config/`: the project. `settings/{base,local,test,production}.py`, `env.py` (typed env readers), `validation.py` (`validate_production`), `urls.py`, `wsgi.py`.
- `backend/rms/<context>/`: one Django app per bounded context, with `api/ services/ domain/ data/ tests/`, created by the change that introduces the context.
- `backend/rms/core/`: cross-cutting technical code only (error envelope, DenyAll, request ID, security headers, logging, health). It holds no domain model and no business rule.
- `manage.py` defaults to `config.settings.local`. `wsgi.py` defaults to `config.settings.production`, so a deploy without an explicit settings module fails closed. There is no `asgi.py` until realtime (Phase 5).

### Settings
- Read environment variables only through `config.env` (`require_str`, `get_str`, `get_bool`, `get_int`, `require_int`, `get_list`, `get_choice`, `get_proxy_ssl_header`). Each raises `ImproperlyConfigured`.
- **Error messages name the variable and the rule, never the value**, for every reader and every validation rule (SC-01).
- Booleans accept exactly `true/false/1/0` (case-insensitive, after strip). Anything else raises. Lists strip entries and reject empty entries.
- No settings module contains a secret literal or a default for `DJANGO_SECRET_KEY` or any `DB_*_PASSWORD`. `test.py` uses `DJANGO_SECRET_KEY` from the environment if set, otherwise a per-process `secrets.token_urlsafe(64)`.
- `local.py` and `test.py` allow only loopback hosts (`localhost`, `127.0.0.1`, `[::1]`; plus `testserver` in tests). `test.py` also refuses a non-loopback `DB_HOST`, and refuses a `DB_NAME` equal to the test DB name (the constant `test_rms`).
- **Every non-local, non-test settings module must end with `validate_production(globals())`** (SC-07). The rules are listed in `config/validation.py` and change 0003 (6.2 rules 1-6, SC-05 rules 7-12). CI runs `check --deploy --fail-level WARNING` on the production settings. The only silenced check is `security.W021` (HSTS preload is a separate decision).
- `SECURE_PROXY_SSL_HEADER` is set only from `DJANGO_SECURE_PROXY_SSL_HEADER=HTTP_<NAME>=https`, and only behind a proxy that overwrites that header (`operations.md`).
- No `django.contrib` app is installed: no admin, auth, sessions, contenttypes, staticfiles. Nothing mounts an admin URL. Importing `rest_framework.views` loads `rest_framework.schemas`, whose `generators` module imports `django.contrib.admindocs.views`; that module in turn imports `django.contrib.admin` and `django.contrib.auth` modules. These are module imports only: none of these apps is installed and nothing is routed.
- Cookie names: `rms_csrf`/`rms_session` in local and test, `__Host-rms_csrf`/`__Host-rms_session` in production. The frontend reads the CSRF cookie by these names.

### Endpoints and permissions
- DRF renders and parses JSON only (no browsable API). `DEFAULT_AUTHENTICATION_CLASSES` is empty and `UNAUTHENTICATED_USER` is `None` until 0005 replaces them.
- `DEFAULT_PERMISSION_CLASSES = [DenyAll]` (`rms.core.api.permissions`). **Every view declares `permission_classes` itself.** Relying on the default does not count, and the route-inventory test rejects it.
- Route inventory (`config/tests/test_routes.py`): every route is either listed in `PUBLIC_ROUTES` or a DRF view that declares a non-`AllowAny` permission. Adding to `PUBLIC_ROUTES` needs a threat-model entry in the change record. Today only `health/live` and `health/ready` are public.
- Test-only views live under a `tests/` package. They are mounted only through a test URLconf with `@pytest.mark.urls(...)`, never in `config/urls.py`.
- Public views also set `authentication_classes = []` and restrict `http_method_names`, so that `OPTIONS` metadata is not served.
- **CSRF carry-forward (SC-15):** DRF views are `csrf_exempt`, and DRF enforces CSRF only inside `SessionAuthentication` for an authenticated user. **0005 must enforce CSRF on every unsafe method, authenticated or anonymous (C6-3/TM-03), and test it on a DRF view.** `CsrfViewMiddleware` stays installed. `CSRF_FAILURE_VIEW` returns the envelope.
- DRF viewsets only for plain resources. Command endpoints are explicit actions. Serializers allow-list fields (`fields = [...]`, never `__all__`).
- **Planned (0006):** each view declares its `required_permission` code, checked by the single authorization helper.
- Tenant views: see "Tenant plane" below.

### Tenant plane (change 0004)
Design: `docs/architecture/tenancy.md`. Every rule below has a test or a scan that fails when it is broken.

**Tenant views**
- Route every tenant endpoint as `api/v1/r/<uuid:tenant_id>/…` (the `uuid` converter, never `str`), to a subclass of `rms.tenancy.api.views.TenantAPIView`. From 0005/0006, subclass `rms.access.api.MemberTenantAPIView` instead; until then `check_principal` is closed and every tenant request is 404, so no tenant route is mounted in `config/urls.py`.
- Declare `permission_classes` (non-`AllowAny`) like every view.
- Never override `dispatch`, `initial`, `resolve_active_tenant`, `check_principal` or `as_view` (they are `@final`; a scan also fails on any override outside `tests` packages and the reviewed allow-list).
- The tenant is `self.tenant` (`ResolvedTenant`: `id`, `status`). Never read a tenant ID from the body, query string or headers.
- The whole request runs in one transaction. A response with status ≥ 400 rolls it back, so a handler can raise or return an error after a partial write. Do not catch a database error and return a success: that becomes a 500. Never return a streaming response from a tenant view (500).
- Services never open `tenant_transaction`; they run inside the one the view opened (or a job runner's, later) and fail with `TenantContextMissing` without it.

**Tenant-owned models**
- Inherit `rms.tenancy.data.models.TenantOwnedModel`. It provides `id` (UUID, server-generated), `tenant` (column `tenant_id`, not editable) and `UNIQUE (tenant_id, id)`. If the model declares `Meta.constraints`, start with `*TenantOwnedModel.Meta.constraints`, and subclass `TenantOwnedModel.Meta`.
- Never add another manager, and never set `objects` to anything but `TenantManager`. Outside `tenant_transaction` every access path raises `TenantContextMissing` (this is the point). `raw()` and `extra()` raise. Do not use `connection.cursor()`, `RawSQL` or `QuerySet(model=…)` outside `rms/tenancy/data/` (scanned).
- `id` and `tenant` are immutable: `update()`, `bulk_update()` and `save(update_fields=…)` raise if they name them, and the app role has no UPDATE on those columns. `save()` and `bulk_create()` fill `tenant` from the context and raise `TenantMismatch` for another tenant.
- Every unique constraint and index leads with `tenant`. Uniqueness that the business defines per restaurant is `UniqueConstraint(fields=["tenant", …])`.
- An FK to another tenant-owned model: `ForeignKey(..., db_constraint=False, db_index=False)`, an index on `(tenant, <fk>)`, and `composite_tenant_fk` in the migration. No `ManyToManyField` with an auto-created through table (use an explicit tenant-owned through model). Only the inherited `tenant` field may reference `Restaurant`; platform tables never reference tenant tables.
- Never `select_related("tenant")` or read `tenant.created_at`/`updated_at`: the app role may read only `id`, `name` and `status` of the registry, so the query fails with "permission denied". Use `self.tenant` in views, or `obj.tenant_id`.
- Serializers for tenant models never accept `id` or `tenant` as input (C-16). A client-chosen ID could collide with another tenant's row and reveal that it exists.
- No sequences or identity columns on tenant tables (they are cross-tenant counters). A per-restaurant counter is designed with `data-engineer`.

**Migrations for a tenant-owned table**
- Migrations run only as the migrator (`make migrate`, `--database migrator`). In the **same migration** as the table's `CreateModel`, add (a test fails otherwise):

  ```python
  from rms.tenancy.data.rls import composite_tenant_fk, enable_tenant_rls, restrict_tenant_key_update

  operations = [  # illustrative model and table names
      migrations.CreateModel(name="Order", ...),
      enable_tenant_rls("orders_order"),                       # ENABLE + FORCE + the tenant_isolation policy
      restrict_tenant_key_update("Order", ["status", "note"]),  # app-role UPDATE on these columns only
      composite_tenant_fk("orders_order", "table_id", "floor_table"),  # one per tenant-to-tenant FK
  ]
  ```
- A column added later is not updatable by the app role until a migration calls `grant_update_columns("<Model>", ["<field>"])`; until then an UPDATE of it fails with "permission denied".
- **Data migrations** over tenant data use `for_each_tenant(apps, schema_editor, fn)` in an atomic `RunPython` (the default; it raises otherwise). It calls `fn(tenant_id)` once per registry row with that tenant's context set on the migration connection. RLS is forced for the migrator too, so `fn` sees only that tenant's rows, but must still filter explicitly: `Model.objects.filter(tenant_id=tenant_id)` on the historical model.
- Never write `set_config`, `SET app.*`, `ALTER ROLE/DATABASE … SET app.*` or libpq `-c app.*` anywhere else; a scan over `backend/` and `scripts/` allows them only in `rms/tenancy/data/context.py` and `rms/tenancy/data/rls.py`.
- A new table without `tenant_id` must be added to the catalog check's platform allow-list (`PLATFORM_TABLES`) and the model to `PLATFORM_MODELS` (`test_models.py`): a security review item.

### Errors
- `rms.core.api.errors` is the one place errors become responses: the DRF `EXCEPTION_HANDLER` plus Django's `handler400/403/404/500` and the CSRF failure view.
- The DRF `EXCEPTION_HANDLER` calls DRF's `set_rollback()` before returning an error response, as DRF's own handler does. With `ATOMIC_REQUESTS` on, a handled 4xx after a partial write therefore rolls the request transaction back instead of committing it (`test_errors.py`, rollback tests). `set_rollback()` acts only on `ATOMIC_REQUESTS` aliases; a service that opens its own `transaction.atomic()` rolls back because the exception leaves the block.
- The envelope is `{"error": {"code", "message", "request_id", "fields"?}}`. `message` is a static string per `code` from `MESSAGES`. Never put the request path, method, parser detail, exception text or CSRF reason in a response. `fields` is only for validation errors.
- A new error code is added to `MESSAGES` with a user-safe message. Unknown exceptions become `500 server_error`.

### Logging
- One JSON object per line on stdout. Fields: `ts, level, logger, message, request_id, tenant_id, membership_id, extra, exc_type` (plus `exc`, the traceback, when there is an exception).
- Pass data as `extra={...}` with descriptive keys. The redaction filter replaces the value of any key containing `password, passwd, secret, token, key, authorization, cookie, session, csrf, pin, otp, credential, auth, bearer, signature, dsn, salt, hash, private`, recursively, on copies.
- **Never pass a secret as a positional log argument** (`logger.info("%s", value)`): key redaction cannot see positional arguments (SC-19e). The formatter also replaces the configured secret key and DB passwords anywhere in a line, but that is the last resort, not the mechanism.
- Only JSON-native values are serialised; other objects become their type name. Django's `request` extra becomes `{method, path}`. Request bodies are never logged.
- `django.db.backends` never logs below WARNING, whatever `LOG_LEVEL` says, so SQL with bound parameters is never logged.
- Per-request context lives in `rms.core.context` contextvars. Set with `token = var.set(...)` and reset with `var.reset(token)` in `finally`. `tenant_id` is bound by `TenantAPIView` after tenant resolution and reset inside the tenant transaction (0004); `membership_id` stays `None` until 0005.
- The request ID is always generated server-side (UUID4). An inbound `X-Request-ID` is ignored.

### Tests
- pytest + pytest-django against PostgreSQL 16 (the compose `db` service). Migrations are not disabled (RLS will live in migrations).
- **Tests connect as the app role** (C3-7). In `test.py`, the `migrator` alias creates and migrates `test_rms` from `rms_template`, and `default` (app role) mirrors it. In Django 5.2 a mirror copies only `NAME`, so `default` keeps the app role's credentials. `migrator` sets `TEST["DEPENDENCIES"] = []`: otherwise Django makes it depend on `default`, which is a mirror and is never created.
- `conftest.py` overrides `django_db_setup` to always set up both aliases, because Django applies a mirror even when its target was not set up. Without the override, `default` would point at the dev DB. After setup, conftest revokes PUBLIC's privileges on the test DB (database ACLs are not copied from a template). A session-scoped guard then aborts the whole run (exit code 3) if any check in `config/tests/db_guards.py` fails.
- Tests declare only `default`. A test that needs the migrator connection declares `databases=["default", "migrator"]`.
- **Transactional tests include `migrator` (SC-29, built in 0004).** Django never flushes a mirror alias, so a transactional test that declares only `default` would keep its committed rows. With `migrator` declared, the flush runs there, as the table owner. An autouse guard fails any transactional test (`transaction=True`, `transactional_db`, `live_server`, `django_db_serialized_rollback`, a `TransactionTestCase` that is not a `TestCase`) that omits it. No alias is serialized, so `serialized_rollback` is unavailable.
- **Tenant data tests use the isolation harness** (`rms.tenancy.tests.harness`):
  - Mark them `@ISOLATION_DB` (transactional, both aliases) and take the `two_tenants` fixture (tenants A and B, committed by the migrator). Context-sensitive tests must be transactional: inside a test transaction the durable `tenant_transaction` is only a savepoint, and registry rows created by the migrator are invisible to the app role.
  - `two_tenants` first asserts that the registry is empty. Because every tenant row needs its registry row (FK) and only the migrator can create one, that proves no earlier test left tenant rows behind.
  - Create tenant rows inside `with tenant_transaction(tenant.id):` with the factories (`make_parent`, `make_child`; `make_restaurant` for extra registry rows, e.g. suspended tenants). Each new tenant model gets its own factory next to its tests.
  - Assert "no row" or "B unchanged" with `rows_visible_to(tenant_id, Model)` and pair it with a positive control in the same test. Never count a tenant table through the migrator without context: the policy binds the migrator too, so the answer is always 0.
  - Every tenant endpoint gets the cross-tenant tests in `docs/architecture/tenancy.md` "Required checks".
- pytest 9 captures non-propagating loggers too (the `django` logger does not propagate). Use `caplog` directly; do not attach `caplog.handler` by hand.
- Factories: factory_boy, in each context's `tests/factories.py`, with deterministic sequences (no Faker data).
