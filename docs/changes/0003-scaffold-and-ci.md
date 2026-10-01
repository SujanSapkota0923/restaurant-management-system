# 0003 — Repository scaffold, local dev and CI

- **Status:** Done (accepted by product owner, 2026-10-01)
- **Risk level:** L3 — raised by orchestrator at gate 4 (architect recommendation): settings/secret loading, cookie/CSRF/host settings and DB role bootstrap are the core of this change; roadmap Phase 2 is L3 throughout. Security review blocking; human approval after design and at acceptance.
- **Requested by / date:** product owner (Phase 2 opened), 2026-09-30
- **Current gate:** 12 (Acceptance) — complete

## 1. Request
First Phase 2 change: create the Django + DRF backend and React + TypeScript + Vite PWA frontend skeletons, local development environment, and CI pipeline, per ADR-0004. No domain models, no tenancy, no auth — those are separate changes (planned: 0004 tenancy + RLS harness, 0005 identity & sessions, 0006 authorization core, 0007 audit core, 0008 frontend app shell).

## 2. Requirements
Goal: a developer (or agent) can clone, start everything locally with one command, run all checks with one command, and CI runs the same checks on every push.

Acceptance criteria:
1. `backend/` Django project (Python 3.12+, Django 5.2 LTS, DRF) managed with uv; settings split by environment, loaded from environment variables with validation at startup.
2. Production settings refuse to start when: `DEBUG` is on, `SECRET_KEY` missing/weak, `ALLOWED_HOSTS` empty or wildcard, or CORS wildcard with credentials. Covered by tests.
3. Secure defaults in production settings: secure cookies, HSTS, `SECURE_PROXY_SSL_HEADER` only if configured, `X_FRAME_OPTIONS=DENY`, no Django admin URL mounted by default.
4. Health endpoints `/health/live` and `/health/ready` (ready checks DB); no auth, no data, tested.
5. Standard API error envelope (`docs/conventions/api.md`) and request-ID middleware in place with tests (no domain endpoints yet).
6. Structured JSON logging with request ID; a redaction filter for secret-like keys, tested.
7. `frontend/` React 18+/TypeScript strict/Vite app, installable PWA manifest, Tailwind, TanStack Query, React Router; renders a placeholder shell at 360px; API client stub handling the error envelope + CSRF header; Vitest test passing.
8. Local dev: `docker compose` with PostgreSQL 16 (+ services the design needs); no secrets committed; `.env.example` with placeholders only.
9. One command each for: setup, run, lint/format check, type-check, test (backend and frontend).
10. CI (GitHub Actions unless the design says otherwise): lint, type-check, tests (backend against real PostgreSQL), `pip-audit`, `npm audit --omit=dev`, secret scan, migration check (`makemigrations --check`).
11. `.claude/rules/` path globs match the real layout (update if the layout differs from `backend/`, `frontend/`).
12. `docs/conventions/backend.md` / `frontend.md` "If ADR-0004 is accepted" sections finalised to the actual choices.

Out of scope: tenancy, users, auth, permissions, audit, any domain model, deployment.

Open questions: none blocking; tool choices within ADR-0004 are `REVIEW`.

## 3. Impact analysis
*(architect, 2026-09-30.)* The repository has no application code: no `backend/`, `frontend/` or `.github/` exists. So the change breaks nothing, but every file it adds sets a precedent that later changes will follow.

| Area | Effect | Evidence |
|------|--------|----------|
| Bounded contexts | None created. Adds only a technical package `rms/core` (error envelope, request ID, logging, health). It holds no domain model and no business rule, and the ubiquitous language is unchanged | `domain-model.md` "Bounded contexts"; `overview.md` "Layering" |
| Data | No models and no app migrations. Creates the local and CI database *roles* and a template database. The roles implement the illustrative table in `tenancy.md` "Database roles"; they do not change it | `tenancy.md` roles table; ADR-0003 C3-5/6/7/10 |
| API contracts | Adds `/health/live` and `/health/ready`, plus the JSON envelope for 404/405/500 and CSRF failure. There are no `/api/v1` endpoints yet | criteria 4–5; `conventions/api.md` "Error envelope" |
| Permissions | No catalog change. DRF defaults to deny-all. The health endpoints are explicitly public and need a threat-model entry (gate 5) | `.claude/rules/security.md`; `authorization.md` |
| Tenant boundary | No tenant resolution yet. The app role is created non-owner with no `BYPASSRLS`, and tests connect as that role with a guard test. The design leaves room for the 0004 tenant-transaction entry point, the migrator alias and the scheduler role | ADR-0003 C3-4/6/7/8 |
| Auth / sessions | None. `django.contrib.auth`, `sessions` and `admin` are **not** installed, so 0005 can add a custom user model and the C6-4 session store without migration debt | ADR-0006 C6-4/C6-5 |
| Config / secrets | New settings loading from env, production validation, cookie/CSRF/HSTS settings and an env example file. **L3 trigger** ("secret/config loading, CORS/CSRF/cookie settings") | `risk-and-approval.md` escalation triggers |
| UI | Placeholder shell only | criterion 7 |
| Background jobs | None. Job queue deferred (see 4) | ADR-0004 "decide in Phase 2" |
| Audit | None. Nothing auditable happens yet | `audit-logging.md` |
| Docs | `conventions/backend.md` and `frontend.md` (criterion 12), `process/testing-strategy.md` (tools and CI), `process/operations.md` (local dev and CI sections), root `README.md` (setup), `CHANGELOG.md`, `architecture/tenancy.md` (note the local/CI role names once data-engineer confirms them) | `docs/README.md` owners |
| `.claude/rules` globs | They match the planned layout, so no change is required (see 6.9) | `.claude/rules/*.md` `paths:` |

**Risk level: raise to L3 for the whole change** (orchestrator decides). Reason: settings/secret loading and cookie/CSRF settings are central to this change, not a side part, and `roadmap.md` Phase 2 says "Critical risk (L3) throughout". Consequence: security review is blocking, and human approval is needed before implementation and before acceptance.

**Must not change:** all ADRs; the permission catalog and role templates; `domain-model.md`; the `tenancy.md` design (only role names may be filled in); `.claude/` and `CLAUDE.md` (6.9 is a proposal only); no code copied from `../rms`. No `django-tenants`, SimpleJWT, Redis, CORS library, Django admin, `contrib.auth` or `contrib.sessions`.

## 4. Architecture decision
*(architect.)* No new ADR is needed: every choice falls inside ADR-0004 (tool choices are `REVIEW`) or implements ADR-0003 as accepted. There is no new context, service or datastore.

- **Modular-monolith layout:** `backend/config/` (project) and `backend/rms/<context>/` (one Django app per bounded context, created by the change that introduces it). The cross-cutting technical code goes in `rms/core`. Alternative: a top-level `common/` package. Rejected, because keeping one import root (`rms.`) makes the future import-boundary lint simpler. — AUTO (matches `conventions/backend.md`)
- **Fewest dependencies:** plain `os.environ` with a small typed reader, not django-environ. Stdlib `logging` with an in-house JSON formatter, not structlog. Discrete `DB_*` variables, not `dj-database-url`. `fetch`, not axios. No CORS package: the deployment is same-origin (ADR-0006 C6-1, security control 16). — REVIEW
- **Job queue: deferred.** Nothing in 0003–0004 needs one. The first change that needs async work (probably 0005 email) decides it, with an ADR. Lean: a PostgreSQL-backed queue, consistent with "no Redis" (C6-5). — REVIEW
- **OpenAPI tooling (`drf-spectacular`): deferred** to the first `/api/v1` endpoint (0005/0006). — REVIEW
- **Playwright, react-hook-form, zod, factory_boy, an i18n library: deferred** until the first change that uses them (0008 for the UI ones, 0004 for factories). — AUTO
- **Tests as the app role now** (C3-7), using a migrator alias that builds the test DB (6.5). Doing this from day one stops CI from becoming comfortable with an owner or superuser connection. — REVIEW (data-engineer + security-engineer)
- **CI runs Postgres through the same `compose.yaml`** as local dev, not a GitHub `services:` container. Service containers start before checkout, so they cannot mount the role-bootstrap script, and they would need a literal password in the workflow. Compose gives parity and passwords generated per run. Trade-off: slightly slower job start. — REVIEW

## 5. Security analysis
*(security-engineer, gate 5, 2026-09-30. Mode 1: threat model of the design in 3, 4 and 6. IDs: `T3-nn` = threat in this change, `SC-nn` = required control. The platform `TM-nn` IDs in `security.md` are referenced where a control here is the first implementation of one. **Verdict: PROCEED WITH CONTROLS.** Every SC below is a required change to section 6 unless it is marked "recommended".)*

### 5.1 Scope
- **Assets:** the framework secret key and DB credentials (superuser, `rms_migrator`, `rms_app`); the DB role and privilege layout, which becomes the RLS backstop in 0004 (R1, R12); the truthfulness of the test suite, because tests that run as the wrong role or against the wrong DB give false assurance of isolation; CI integrity (the pipeline that will later gate every tenant and money change); developer machines; the production configuration that later deploys inherit.
- **Actors:** A1 anonymous internet (health endpoints and error paths, once deployed); A8 a compromised dependency, GitHub Action, container image or fork PR; a local process on a developer machine; a well-meaning developer or agent who misconfigures an environment (the most likely actor in this change).
- **Entry points / trust boundaries:** process environment and the env file → settings (config boundary); `/health/live`, `/health/ready`, every unknown path and every error path (B1); request headers (`Host`, `X-Request-ID`, `X-Forwarded-*`, `Cookie`); log output; `scripts/db/bootstrap.sh` running as the DB superuser; the test-DB creation path (B2); `scripts/dev/init-env.sh`; the CI workflow, its triggers, actions, images and package installs; Dependabot PRs.

### 5.2 Verified facts behind the MIRROR finding
Verified against the installed Django 4.2 source (`~/.pyenv/versions/3.12.13/.../django`). ASSUMPTION: 5.2 is unchanged in these functions; the engineer re-checks against the locked 5.2 version.
- `setup_databases` configures **every** mirror alias unconditionally, even when its target was not set up (`django/test/utils.py:240-244`). That confirms the architect's footgun: `default` then keeps the dev DB name `rms`.
- `set_as_test_mirror` copies only `NAME` (`django/db/backends/base/creation.py:106-111`). The mirror therefore keeps its own `USER`, so `default` stays `rms_app`. Good: MIRROR does not silently turn the tests into migrator connections.
- `TransactionTestCase` flush, fixture loading and sequence reset skip mirror aliases (`django/test/testcases.py:1198,1215,1303,1454`, `include_mirrors=False`). Transactional tests that declare only `default` are therefore **never flushed**, and committed rows carry over into later tests. This is not a vulnerability in 0003 (there are no models yet). In 0004 it would let isolation tests pass on leftover data. Carried to 0004 as SC-29.

### 5.3 Threats and controls
L/I = likelihood / impact (H/M/L, C = critical).

| ID | Entry | Threat | L/I | Control | Test / check |
|----|-------|--------|-----|---------|--------------|
| T3-01 | config | A secret value is echoed in an `ImproperlyConfigured` message (env reader or validation) and reaches the CI log or a crash reporter | M/H | SC-01 | NT3-01 |
| T3-02 | config | A literal fallback `SECRET_KEY` or password in a settings module (especially `test.py`) is committed, becomes a known key, and trips gitleaks forever after | M/H | SC-02 | NT3-02, gitleaks |
| T3-03 | config | Lenient bool parsing (`"False "`, `"no"`, `"off"` read as truthy) turns `DEBUG` on | M/H | SC-03 | NT3-03 |
| T3-04 | config | A deployed process loads `config.settings.local` (inherited `DJANGO_SETTINGS_MODULE`, or the `manage.py` default) and runs with DEBUG pages and insecure cookies | M/H | SC-04 | NT3-04 |
| T3-05 | 6.2 | The production validation misses settings that silently weaken prod: cookie `HttpOnly`/`SameSite`/`__Host-` constraints, SSL redirect, forwarded host, a foreign trusted CSRF origin, secret-key fallbacks | M/H | SC-05 | NT3-05 |
| T3-06 | 6.2 | `SECURE_PROXY_SSL_HEADER` is set without a proxy that overwrites the header, or is loosely parsed, so the client can claim HTTPS (bypassing the SSL redirect and `is_secure()`) | L/M | SC-06 | NT3-06 |
| T3-07 | 6.2 | Validation is skipped: `production.py` is edited, or a future staging module forgets the call | M/H | SC-07 | NT3-07, CI `check --deploy` |
| T3-08 | B1 | Host-header poisoning (TM-30 precedent); Django's default HTML 400 on `DisallowedHost` | M/M | 6.2 rule 3 + SC-05 (`USE_X_FORWARDED_HOST`) + SC-13 | NT3-13 |
| T3-09 | health | Health output discloses version, DB error text or host names | M/L | 6.3 (fixed body, generic 503, only the exception class is logged) + SC-10 | NT3-09 |
| T3-10 | health | Unauthenticated `/health/ready` opens a new DB connection per request (`CONN_MAX_AGE=0`, and libpq has no connect timeout by default). Flooding it exhausts worker threads and `max_connections` | M/M (once deployed) | SC-10; rate limit deferred (proposed R25, 5.6) | NT3-10 |
| T3-11 | all routes | Default-open drift (**permission threat**): a later change adds a route with no permission, or with `AllowAny`, and nothing notices | M/H | SC-11 | NT3-11 |
| T3-12 | health | Health or error responses cached by intermediaries or the service worker | L/L | 6.3 `no-store` + 6.4 SW denylist (no new SC) | NT3-12 |
| T3-13 | errors | Verbose or reflected errors: DRF `ParseError` detail, a 404 message that echoes the path, the CSRF `reason` (which contains the attacker's Origin/Referer), Django's default HTML 400/403 | M/M | SC-13 | NT3-13 |
| T3-14 | errors | A test-only view (raising view, CSRF probe) ends up in the production URLconf | L/H | SC-14 | NT3-11 |
| T3-15 | CSRF | Precedent: DRF's `APIView.as_view()` is `csrf_exempt`, and DRF enforces CSRF only inside `SessionAuthentication` for an authenticated user. If 0005 is unaware of this, anonymous unsafe endpoints (login, signup, reset) have no CSRF (TM-03) | H/H (in 0005) | SC-15 | NT3-15; NT-03 in 0005 |
| T3-16 | headers | Security headers missing on error responses because of middleware order | M/L | 6.3 + SC-16 | NT3-16 |
| T3-17 | request ID | Log forging through an inbound `X-Request-ID` (CRLF, very long values, a chosen ID) | M/L | 6.3 (inbound value ignored) | NT3-17 |
| T3-18 | request ID | The contextvar is not reset, so a WSGI thread carries one request's ID (and, from 0004, its `tenant_id`) into the next request or into out-of-request logs: cross-tenant misattribution in logs (tenant side channel) | M/M | SC-18 | NT3-18 |
| T3-19 | logging | Secrets reach logs by paths that key-based redaction cannot see: positional `%`-args, the formatted message, exception text, Django's `request` extra, SQL debug logging with bound parameters when `LOG_LEVEL=DEBUG` | M/H | SC-19 | NT3-19 |
| T3-20 | logging | The redaction filter raises (cycle, deep nesting, odd type) and drops or crashes logging; or it mutates the caller's `extra` dict | M/M | SC-20 | NT3-20 |
| T3-21 | logging | Log injection through newlines in attacker-controlled values (Host, path, CSRF reason) | M/L | JSON encoding (6.3) | NT3-21 |
| T3-22 | bootstrap | SQL injection or password exposure in `bootstrap.sh`. psql does not interpolate `:'var'` inside `DO $$…$$` blocks, which invites shell-built SQL. `-v pw=…` puts passwords on argv, where the process list shows them. A failing `ALTER ROLE … PASSWORD` is echoed to the server log (`log_min_error_statement=error`), which `docker compose logs` then prints into CI | M/H | SC-22 | NT3-22 |
| T3-23 | DB auth | DB host auth is `trust` or `md5`; the port is bound beyond loopback | L/H | SC-23 | NT3-23 |
| T3-24 | DB roles (**tenant threat**, R1/R12) | The app role has more privilege than designed: database ACLs are **not** copied from a template, so Django-created `test_rms` gives `PUBLIC` `CONNECT`+`TEMP`; membership in any role, not only the migrator; ownership of objects | M/C (from 0004) | SC-24 | NT3-24 |
| T3-25 | tests (**tenant threat**, R12) | Tests run as the wrong role or against the wrong DB (MIRROR footgun, verified in 5.2), or against a non-local server whose same-named test DB the runner drops without asking | M/C | SC-25 | NT3-25 |
| T3-26 | init-env | Weak or predictable generated secrets; values printed to stdout or the CI log; world-readable file; an existing env file overwritten; placeholders left in place; characters that break compose `$` interpolation or `--env-file` parsing | M/M | SC-26 | NT3-26 |
| T3-27 | env file | The env file is committed or left untracked-but-not-ignored (the file name drifts from `.gitignore`) | L/C | SC-27 | NT3-27 |
| T3-28 | compose | The whole env file (including `DJANGO_SECRET_KEY`) is injected into the DB container; `docker compose config` prints interpolated secrets | M/M | SC-28 | review |
| T3-29 | tests (0004) | Transactional tests never flushed on a mirror alias (5.2), so isolation tests pass on leftover rows | M/H (0004) | SC-29 (carried) | 0004 |
| T3-30 | CI | Poisoned pipeline: `pull_request_target`, `workflow_run` or comment triggers run fork code with a write token or secrets | L/C | SC-30 | NT3-30 |
| T3-31 | CI | Token theft: `actions/checkout` stores `GITHUB_TOKEN` in `.git/config`, readable by dependency install scripts and by containers that mount the repo (gitleaks) | M/M | SC-31 | NT3-30 |
| T3-32 | CI | Mutable references: action tags, image tags (`postgres:16`, gitleaks), unpinned `uvx pip-audit`, `setup-uv` installing the latest uv | M/H | SC-32 | NT3-30 |
| T3-33 | CI | Script injection through `${{ github.event.* }}` / `github.head_ref` in `run:` | L/H | SC-33 | NT3-30 |
| T3-34 | CI | Malicious dependency code runs in CI (install scripts) or lockfile/manifest drift goes unnoticed | M/H | SC-34 | CI |
| T3-35 | CI | Known-vulnerable dependencies ship, including in the build toolchain that produces the shipped bundle and runs the dev server | M/H | SC-35 | CI |
| T3-36 | CI | gitleaks prints found secrets into the CI log (its default); a broad allow-list hides real findings | M/H | SC-36 | NT3-36 |
| T3-37 | CI | The env file or env values leak through artifacts or debug steps (`upload-artifact` of the workspace, `env`, `printenv`, `docker compose config`) | L/M | SC-37 | review |
| T3-38 | CI/repo | CI is advisory only (no required checks); fork workflows run without approval | M/H | SC-38 (human, GitHub settings) | human |
| T3-39 | Dependabot | A malicious new version merges through an automated PR (npm worm class) | M/H | SC-39 | review |
| T3-40 | frontend | The API client sends `X-CSRFToken` and credentials to an absolute or protocol-relative URL | L/M | SC-40 | NT3-40 |
| T3-41 | frontend | Server secrets end up in the client bundle (Vite `envDir` pointed at the repo root, secret `VITE_*` vars) | L/H | SC-41 | NT3-41 |
| T3-42 | dev | The Vite dev server is exposed on the LAN (`server.host: true`), which with its file-serving CVE history means file disclosure from a developer machine | L/M | SC-42 (recommended) | review |

### 5.4 Required controls (changes to section 6)
**Config and secrets (6.2, 6.6)**
- **SC-01** `env.py` readers and `validate_production` never put a variable's *value* in any message: name and rule only (e.g. "DB_PORT must be an integer"). This applies to every reader type, not only secrets.
- **SC-02** No settings module contains a literal secret key or password, and there is no default for `DJANGO_SECRET_KEY` or `DB_*_PASSWORD`. `local.py` and `production.py` raise if they are missing. `test.py` uses `DJANGO_SECRET_KEY` from env if it is set, and otherwise `secrets.token_urlsafe(64)` generated per process.
- **SC-03** The bool reader accepts exactly `true/false/1/0` (case-insensitive, after strip) and raises on anything else. `DJANGO_DEBUG` defaults to `false` in every module when it is unset.
- **SC-04** `local.py` and `test.py` hard-limit `ALLOWED_HOSTS` to a subset of `{localhost, 127.0.0.1, [::1]}` (the `testserver` host may be added in `test.py`). If `DJANGO_ALLOWED_HOSTS` lists anything else, they raise `ImproperlyConfigured`. A mis-selected dev module then cannot serve a real hostname.
- **SC-05** Add these rules to `validate_production` (6.2), numbered on from 6:
  7. `SESSION_COOKIE_HTTPONLY` is false, or either cookie's `SAMESITE` is not in `{"Lax","Strict"}`;
  8. either cookie name does not start with `__Host-`, or `SESSION_COOKIE_DOMAIN`/`CSRF_COOKIE_DOMAIN` is not `None`, or either cookie path is not `/`;
  9. `SECURE_SSL_REDIRECT` is false, `SECURE_CONTENT_TYPE_NOSNIFF` is false, or `X_FRAME_OPTIONS != "DENY"`;
  10. `USE_X_FORWARDED_HOST` or `USE_X_FORWARDED_PORT` is true;
  11. a `CSRF_TRUSTED_ORIGINS` entry has a host that is not in `ALLOWED_HOSTS`, or has a path (extends rule 5: same-origin deployment, C6-1);
  12. any `SECRET_KEY_FALLBACKS` entry fails rule 2.
  The list reader strips entries and rejects empty ones, so `" *"` and `"a,,b"` cannot slip past rule 3.
- **SC-06** `DJANGO_SECURE_PROXY_SSL_HEADER` is parsed strictly as `NAME=https`, with `NAME` matching `^HTTP_[A-Z0-9_]+$`; anything else raises. `docs/process/operations.md` states that it may be set only behind a proxy that overwrites that header (Phase 10 deploy check).
- **SC-07** CI (backend job) runs `manage.py check --deploy --fail-level WARNING` with `DJANGO_SETTINGS_MODULE=config.settings.production` and generated values. `conventions/backend.md` states that every non-local, non-test settings module must end with `validate_production(globals())`.

**Endpoints, errors, headers (6.3)**
- **SC-10** The `default` alias sets `OPTIONS={"connect_timeout": 5}` (data-engineer may lower it). Readiness runs only `SELECT 1` under the role's `statement_timeout`. The body carries no version, commit or host.
- **SC-11** Route-scan test (first form of NT-11): it enumerates every resolvable URL pattern and fails unless the set equals an explicit `PUBLIC_ROUTES` allow-list (`health/live`, `health/ready`) plus routes whose view declares a non-`AllowAny` permission. Adding to `PUBLIC_ROUTES` needs a threat-model entry. A test also checks that a test-only DRF view with no declared permission gets 403 with the envelope (DenyAll default).
- **SC-13** Add `handler400` and `handler403` (envelope) next to 404/500. Every envelope `message` is a static string per `code`: no request path, method, parser detail or CSRF `reason` in the body. The CSRF reason goes only to the log, at WARNING. Every error response is `application/json`.
- **SC-14** Test-only views live under `tests/` and are mounted only via `override_settings(ROOT_URLCONF=...)`. SC-11 fails if one reaches `config/urls.py`.
- **SC-15** A test asserts that `CsrfViewMiddleware` is in `MIDDLEWARE`. The `csrf_failed` test runs the real Django CSRF check on a plain (non-DRF) test view and asserts the envelope. `conventions/backend.md` records the carry-forward: *DRF views are `csrf_exempt`; 0005 must enforce CSRF on every unsafe method, authenticated or anonymous (C6-3/TM-03), and test it on a DRF view.*
- **SC-16** The security-headers test covers 200, 404, 405, 500, 400 (bad Host) and 403 (CSRF) responses: `Cache-Control: no-store`, the CSP, `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `X-Request-ID`.
- **SC-18** The request-ID middleware uses `token = var.set(...)` and `var.reset(token)` in `finally`. The same mechanism is reserved for `tenant_id` and `membership_id` (0004/0005). The envelope's `request_id` equals the response header, on the 500 path too.

**Logging (6.3)**
- **SC-19** (a) The `django.db.backends` logger is pinned at `WARNING` or higher whatever `LOG_LEVEL` says. (b) The formatter serialises only JSON-native types. Any other object becomes its type name. The `request` extra that Django attaches becomes `{method, path}`, with no query string, headers or cookies. (c) Known-secret scrub: as its last step the formatter replaces exact occurrences of the configured secret values (`SECRET_KEY`, every `DATABASES[*]["PASSWORD"]`) in the whole serialised line, exception text included. (d) Add `auth`, `bearer`, `signature`, `dsn`, `salt`, `hash`, `private` to the key list. Over-redaction is acceptable. (e) Document the rule "never pass a secret as a positional log argument" in `conventions/backend.md`: key redaction cannot see positional args.
- **SC-20** The filter copies and does not mutate. It has a depth limit (8) and a cycle guard. It never raises: on internal error it replaces the field with `"[REDACTION_ERROR]"` and still emits the record.

**DB bootstrap and test DB (6.5)**
- **SC-22** `bootstrap.sh`: `set -euo pipefail`, never `set -x`. Passwords are read inside psql with `\getenv` (psql 16) from the container environment: never on argv, never echoed. Before any statement that carries a password, it runs `SET log_statement='none'; SET log_min_error_statement='panic';`. Conditional creation uses `SELECT format('CREATE ROLE %I …', :'name') WHERE NOT EXISTS (…) \gexec`: no `DO` blocks with interpolated values, and no shell interpolation of names or passwords into SQL text. Role and DB names are checked against `^[a-z_][a-z0-9_]{0,62}$` before use. `shellcheck` in `lint` is recommended.
- **SC-23** compose sets `POSTGRES_HOST_AUTH_METHOD=scram-sha-256` explicitly and keeps `127.0.0.1:5432:5432`. CI asserts that `docker compose port db 5432` starts with `127.0.0.1:`, and that a TCP login as `rms_app` with a wrong password fails.
- **SC-24** After it creates the test DB, the conftest runs, as the migrator (owner), `REVOKE ALL ON DATABASE <test db> FROM PUBLIC` and `GRANT CONNECT` to the app and migrator roles. Identifiers go through `psycopg.sql.Identifier`. Extend the 6.5 guard tests with: no `TEMP` and no `CREATE` on the current database for `current_user`; **zero** rows in `pg_auth_members` with `member = current_user` (any role, not only the migrator); `rolinherit`, `rolcreatedb`, `rolcreaterole`, `rolreplication` all false; `current_user` owns no database, schema or relation in the current DB.
- **SC-25** (a) Keep the architect's `django_db_setup` override. (b) The 6.5 guards and SC-24 run in a **session-scoped autouse fixture** after DB setup. On any failure it calls `pytest.exit(..., returncode=3)` before any test runs; a single failing test is not enough, because the rest would still run against the wrong DB. It also checks that the `migrator` alias sees `test_rms` and that `default`'s `current_user` equals `DB_APP_USER`. (c) `test.py` raises unless `DB_HOST` is one of `127.0.0.1`, `localhost`, `::1`, the test DB name starts with `test_` and it differs from `DB_NAME`. If MIRROR proves unworkable, the 6.5 `BLOCKED` fallback still applies. Under no fallback may `default` connect as the migrator.
- **SC-29** (carried to 0004, data-engineer/QA) Transactional tests must include the `migrator` alias for teardown flush, or use an equivalent that is proven by a test in which a committed row does not survive into the next test.

**Local secrets (6.1, 6.6)**
- **SC-26** `init-env.sh`: CSPRNG only (`openssl rand -hex` or Python `secrets`). `SECRET_KEY` is at least 64 characters and DB passwords at least 32, alphabet `[A-Za-z0-9]`. `umask 077`: write to a temp file in the same directory, then `mv -n`, final mode `0600`. If the env file exists, exit 0 with a message and no values. Never print a value. Fail if `change-me` remains in the output, or if its key set differs from the example's. In CI, the step after generation registers each generated secret with `::add-mask::` and prints nothing else.
- **SC-27** The committed template is named exactly `.env.example` and the env file `.env`, matching `.gitignore:2-4`. In CI, `git status --porcelain` is empty after `init-env` and the test run.
- **SC-28** The `db` service gets only `POSTGRES_PASSWORD`, `DB_APP_*` and `DB_MIGRATOR_*`, through an explicit `environment:` mapping, never `env_file:` with the whole env file. `docker compose config` never runs in CI or in any `make` target that CI calls. The `postgres:16` image is pinned by `@sha256:` digest **now**, not as a follow-up, because it runs the bootstrap in CI with per-run secrets.

**CI and supply chain (6.7, 6.8)**
- **SC-30** Triggers are `push` and `pull_request` only. `pull_request_target`, `workflow_run`, `issue_comment` and `workflow_dispatch` with inputs are forbidden. A workflow linter enforces this together with SC-31..33: `zizmor` at an exact pinned version (tool choice REVIEW; `actionlint` plus a grep script is an acceptable equivalent), as a step in the `secrets` job.
- **SC-31** Every `actions/checkout` has `persist-credentials: false`. `permissions: contents: read` sits at workflow level and no job raises it. The workflow references no `secrets.*`.
- **SC-32** Every `uses:`, first-party `actions/*` included, is pinned to a 40-hex SHA with a version comment. The gitleaks and postgres images are pinned by digest. `uvx pip-audit==<exact>`. `setup-uv` has `version:` pinned. Node comes from `.nvmrc`.
- **SC-33** No `${{ … }}` expressions from `github.event`, `github.head_ref` or other attacker-influenced contexts inside `run:`; pass them through `env:` if they are ever needed.
- **SC-34** The `audit` job installs nothing: `npm audit` reads `package-lock.json` (no `npm ci`), and pip-audit reads the exported requirements with `--disable-pip`. CI uses `uv sync --locked` (it fails on lock/manifest drift) instead of `--frozen`. Recommended (REVIEW): `npm ci --ignore-scripts` in the frontend job if the build passes with it.
- **SC-35** Thresholds: `pip-audit --strict` fails on any severity (the export includes dev groups). `npm audit --omit=dev --audit-level=low` is blocking, **plus** a full-tree `npm audit --audit-level=high` that is also blocking (the dev toolchain builds the shipped bundle). Any ignore or allow-list entry needs a `docs/risks.md` acceptance by the human, with an expiry date.
- **SC-36** gitleaks runs with `--redact`, over the full history (`fetch-depth: 0`), with the repo mounted read-only (`:ro`). The same flags apply locally. Any `.gitleaks.toml` allow-list is path-scoped only, and each entry is a security-engineer REVIEW.
- **SC-37** No `actions/upload-artifact` of the workspace root or the env file. No `env`, `printenv` or `docker compose config` steps. On failure only `docker compose logs db` is allowed; SC-22 keeps passwords out of it.
- **SC-38** *(human; GitHub repository settings, not code; record in `operations.md`)*: a branch ruleset on `main` with the four CI jobs as required checks; "Require approval for all outside collaborators" for fork PR workflows; default workflow token permission "Read repository contents".
- **SC-39** `dependabot.yml`: no auto-merge. `github-actions`, `npm`, `uv` and `docker-compose` ecosystems (ASSUMPTION: the `docker-compose` ecosystem is available for `compose.yaml`; otherwise update the digest by hand, noted in `operations.md`). Recommended: `cooldown` of 7 days for version updates (security updates exempt).

**Frontend (6.4)**
- **SC-40** The API client accepts only relative paths beginning with `/api/` and rejects absolute and `//` URLs, so the CSRF header and credentials never leave the origin. Test.
- **SC-41** Vite `envDir` stays `frontend/` (never the repo root), and no `VITE_*` variable holds a secret. CI runs gitleaks in `dir` mode over `frontend/dist` after the build.
- **SC-42** *(recommended)* Vite `server.host` stays at its loopback default and `server.fs.strict` stays on.

### 5.5 Required negative tests and checks (QA plan input)
- **NT3-01** For each env reader and each validation rule: the message does not contain the supplied bad value (use a distinctive canary value).
- **NT3-02** Importing `local` or `production` with `DJANGO_SECRET_KEY` unset raises. `test` generates a key of 64 characters or more. gitleaks is clean.
- **NT3-03** `"False "`, `"no"`, `"off"`, `"yes"` → raise. `"true"`, `"0"` parse correctly. Unset → false.
- **NT3-04** `local` with `DJANGO_ALLOWED_HOSTS=example.com` raises.
- **NT3-05** One failing case per rule 7–12, plus `" *"` and an empty-entry case for rule 3.
- **NT3-06** A malformed proxy header value raises; a valid one yields the tuple; unset → `None`.
- **NT3-07** The subprocess test (6.2) plus CI `check --deploy` pass on good values and fail on `DJANGO_DEBUG=true`.
- **NT3-09** DB unreachable → `/health/ready` gives 503 `not_ready`, the body is exactly the envelope, and neither the body nor the log line contains the exception message.
- **NT3-10** With the DB host blackholed, readiness returns within connect timeout + 1 s (mark it slow if needed; no sleeps).
- **NT3-11** The route-scan test (SC-11). Adding an unlisted route makes it fail (self-test with an override URLconf).
- **NT3-12** Health responses carry `Cache-Control: no-store`. A Vitest test on the PWA config asserts the `/api/` and `/health/` denylist and that there is no `/api` runtime caching.
- **NT3-13** A bad `Host` gives a 400 envelope. Malformed JSON on a test view gives a 400 with a generic message. A 404 body does not contain the requested path. The CSRF failure body does not contain the Origin/Referer value. A test view that raises gives a 500 envelope with no exception text. All run with `DEBUG=False` and all are `application/json`.
- **NT3-15** Unsafe POST without a token → 403 `csrf_failed` through the real middleware. `CsrfViewMiddleware` is present.
- **NT3-16** The header matrix of SC-16.
- **NT3-17** An inbound `X-Request-ID` containing CRLF or 10 kB is not reflected. The response ID is a UUID4.
- **NT3-18** After a request (including one that raises), the contextvar is `None`. Two sequential requests have different IDs. A log emitted outside any request has `request_id: null`.
- **NT3-19** With `LOG_LEVEL=DEBUG`, running a query emits no SQL log line. A record whose message or exception text contains the configured `SECRET_KEY` value is emitted with it replaced. A `request` extra serialises without query string or cookies. The new keys are redacted.
- **NT3-20** A self-referencing dict, 50-level nesting and an object with a raising `__repr__` each still produce one valid JSON line. The caller's dict is unchanged.
- **NT3-21** A message containing `\n{"level":"CRITICAL"}` produces exactly one JSON line.
- **NT3-22** CI runs `bootstrap.sh` a second time against the running DB: exit 0, and roles and grants are unchanged. A review checklist item covers SC-22.
- **NT3-23** The SC-23 CI assertions.
- **NT3-24** The SC-24 guard queries.
- **NT3-25** The session guard aborts the run: verified once during implementation by temporarily breaking the override on a local branch (recorded in section 8, not committed). `test.py` with `DB_HOST=db.example` raises.
- **NT3-26** A pytest test runs `init-env.sh` in a temp dir with a copy of the example. It checks: mode `0600`; no `change-me`; key set equals the example's; stdout and stderr contain none of the generated values; a second run leaves the file byte-identical.
- **NT3-27** CI `git status --porcelain` is empty.
- **NT3-30** The workflow linter (SC-30..33) passes in CI and fails on a deliberately bad copy of the workflow (verified once during implementation).
- **NT3-36** gitleaks run once, during implementation, in `dir` mode on a temp directory holding a synthetic private-key header: it exits non-zero and the output shows `REDACTED`. Never commit the canary.
- **NT3-40** The client rejects `https://evil.test/x` and `//evil.test/x`. The CSRF header is sent only on unsafe methods.
- **NT3-41** gitleaks is clean over `frontend/dist`.

### 5.6 Not applicable in this change (one-line reasons)
- **Cross-tenant access (TM-08/10):** there is no tenant data, tenant resolution or tenant endpoint yet. The tenant threats here are the foundation threats T3-18, T3-24, T3-25 and T3-29.
- **Permission misuse and escalation (TM-11/12):** there is no catalog use and no protected action. The permission threat is default-open drift (T3-11), controlled by DenyAll plus the route scan.
- **Replay and races (TM-15):** there is no state-changing endpoint. The only repeatable write is the bootstrap, whose re-run is tested (NT3-22). Superseded CI runs are cancelled, which carries no security effect.
- **Repudiation and audit (TM-18):** nothing auditable happens. Logs carry the request ID.
- **Sessions, login, enumeration, tokens in storage (TM-01..06):** `contrib.auth` and `contrib.sessions` are not installed. The ESLint bans on `localStorage`/`sessionStorage` set the precedent.
- **Uploads, webhooks, SSRF, unsafe deserialization (TM-19, TM-31):** there are no uploads, no provider integration and no outbound URLs. DRF uses the JSON parser only.
- **CORS:** no CORS package, same-origin deployment (C6-1). 6.2 rule 4 stays as a tripwire.

### 5.7 Residual risks, for human acceptance (not accepted by security)
- **Proposed R25:** the unauthenticated `/health/*` endpoints are not rate-limited, which departs from `.claude/rules/security.md` ("Rate-limit … public endpoints"). No rate-limit infrastructure exists yet, and nothing is deployed. Mitigation now: SC-10. Before any deployment (Phase 10), readiness is reachable only from the platform's health checker, or the edge rate-limits `/health/*` per IP. **APPROVAL:** the human accepts this until Phase 10, or asks for an in-process limiter now (not recommended: it does not hold across workers).
- **R16 (existing):** local and CI environments hold both the migrator and the app credentials, and the migrator has `CREATEDB`. This is acceptable below staging. The runtime-env check stays deferred to 0004/Phase 10, as the architect wrote.
- The CI trust boundary relies on GitHub repository settings (SC-38) that code cannot enforce. Until the human applies them, CI is advisory.

### 5.8 `.claude/rules/database.md` glob (6.9)
**Advisable: yes.** `scripts/db/bootstrap.sh` defines the role privileges that make RLS meaningful (R1, R12). Today no path-scoped rule loads when an agent edits it: `**/*.sql` does not match `.sh`. Add `scripts/db/**` to the `paths:` of `database.md`. `database.md`'s current bullets are mostly about models, so its benefit is mainly that it surfaces `data.md`/`tenancy.md`. The security-relevant guidance for this file is SC-22/24, together with the always-on `tenant-isolation.md` and `secrets.md`. A follow-up worth considering: add one bullet to `database.md`: "Role/privilege scripts: least privilege per `tenancy.md` roles table; no string-built SQL; no passwords on argv or in server logs." Both edits change `.claude/`, so they are **APPROVAL** (proposed, not applied). This is non-blocking for 0003.

### 5.9 Verdict
**PROCEED WITH CONTROLS.** Nothing in the design meets a BLOCK condition. It declares a permission on every endpoint (health endpoints explicitly public, and threat-modelled here). It lets no tenant query run without context, because no tenant data exists yet. It puts no secrets in code, stores no JS-readable auth token, and builds no SQL from strings. Implementation may start once the human approves the design under L3. At gate 9 (security review), any SC-01..SC-41 that is missing or untested is a finding. A missing SC-22, SC-24, SC-25, SC-30, SC-31 or SC-36 is `high` or above and blocks.

## Human approval (gate 6, L3) — product owner, 2026-10-01
- Design (sections 5 + 6, including SC-01..SC-42) approved for implementation.
- R25 (health endpoints not rate-limited until Phase 10) accepted.
- `.claude/rules/database.md` paths extended with `scripts/db/**` (applied by orchestrator).
- No GitHub repository yet: CI files are built now; CI is advisory until a repository exists and SC-38 settings are applied (blocking for gate 12 stays as noted; owner to decide at acceptance).
- Where section 5 controls change section 6, section 5 wins.

## 6. Design
*(architect. No application code; exact code is backend/frontend-engineer's. The `data-engineer` confirms role names and timeouts. "Env file" below means the gitignored root dotenv file, and "env example" its committed placeholder template.)*

### 6.1 Layout — AUTO
```
Makefile  compose.yaml  <env example>  .github/{workflows/ci.yml,dependabot.yml}
scripts/dev/init-env.sh      # creates the env file from the example with random secrets if absent; never prints them
scripts/db/bootstrap.sh      # roles + template DB + dev DB (6.5); used by the compose initdb hook and by CI
backend/  pyproject.toml uv.lock .python-version(3.12) manage.py conftest.py
  config/  env.py (typed readers: str/bool/int/list; raise ImproperlyConfigured)  validation.py (pure fn, 6.2)
           settings/{base,local,test,production}.py  urls.py  wsgi.py  tests/
  rms/core/  apps.py  middleware.py (request ID, API security headers)  logging.py (JSON formatter, context + redaction filters)
             health.py  api/errors.py (envelope, DRF exception handler, handler404/500, CSRF failure view)  api/permissions.py (DenyAll)  tests/
  rms/<context>/  api/ services/ domain/ data/ tests/   # later changes, per conventions/backend.md
frontend/ package.json package-lock.json .nvmrc(24) index.html vite.config.ts tsconfig*.json eslint.config.js .prettierrc.json public/icons/
  src/ main.tsx  app/{App,router,providers,AppShell}.tsx  components/ui/  features/<context>/ (from 0008)
       lib/api/{client.ts,errors.ts,client.test.ts}  i18n/messages.ts  styles/index.css  test/setup.ts
```
`manage.py` defaults to `config.settings.local`. `wsgi.py` defaults to `config.settings.production`, so a misconfigured deploy fails closed. No `asgi.py` until realtime (Phase 5). Node 24 is the Active LTS release; the local Node 26 satisfies `engines: ">=24"`.

### 6.2 Settings and startup validation (criteria 1–3) — REVIEW, security-engineer blocking
- `base.py` holds everything shared and secure-by-default. INSTALLED_APPS = `rest_framework`, `rms.core` (no contrib apps). `APPEND_SLASH=False`, `X_FRAME_OPTIONS="DENY"`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY="strict-origin-when-cross-origin"` (TM-08), `CSRF_COOKIE_HTTPONLY=False` (JS reads it, per `api.md`), `CSRF_COOKIE_SAMESITE="Lax"`, `CSRF_FAILURE_VIEW` → envelope.
- DRF settings: JSON renderer and parser only (no browsable API); `DEFAULT_AUTHENTICATION_CLASSES=[]` and `UNAUTHENTICATED_USER=None` (0005 replaces these); `DEFAULT_PERMISSION_CLASSES=[DenyAll]`; `EXCEPTION_HANDLER` → envelope.
- Only the `default` DB alias is defined here, from `DB_HOST/PORT/NAME/APP_USER/APP_PASSWORD`, with `CONN_MAX_AGE=0` until the C3-2 reuse test exists (0004).
- `local.py`: `DEBUG` from env; cookie names `rms_csrf` (and `rms_session`, reserved for 0005); adds the `migrator` alias (`DB_MIGRATOR_*`).
- `test.py`: `DEBUG=False`, the `migrator` alias, `TEST` settings per 6.5.
- `production.py`: `DEBUG=False`, hard-coded. Secure CSRF/session cookies, names `__Host-rms_csrf` / `__Host-rms_session`. `SECURE_HSTS_SECONDS=31536000` with `INCLUDE_SUBDOMAINS`; preload stays off (a separate decision). `SECURE_SSL_REDIRECT=True`. `SECURE_PROXY_SSL_HEADER` is set only if `DJANGO_SECURE_PROXY_SSL_HEADER` is set (format `HTTP_X_FORWARDED_PROTO=https`); otherwise `None`. No `migrator` alias (the migration-job settings come in 0004, C3-6). The module ends by calling `validation.validate_production(globals())`.
- `validate_production` raises `ImproperlyConfigured` and collects *all* failures into one message that names settings only, never values. It fails when:
  1. `DEBUG` is truthy, or env `DJANGO_DEBUG` parses to true;
  2. `SECRET_KEY` is missing, shorter than 50 characters, has fewer than 5 unique characters, starts with `django-insecure-`, or contains the env-example placeholder marker (`change-me`);
  3. `ALLOWED_HOSTS` is empty, or contains `*` or an entry starting with `.` (single host, C6-1);
  4. `CORS_ALLOW_ALL_ORIGINS` is true, or `"*"` is in `CORS_ALLOWED_ORIGINS`, while `CORS_ALLOW_CREDENTIALS` is true. The check is generic, so it still works if a CORS package is ever added (REVIEW);
  5. a `CSRF_TRUSTED_ORIGINS` entry is not `https://` or contains `*`;
  6. `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` is false, or `SECURE_HSTS_SECONDS` < 31536000.
- Tests (`config/tests/test_validation.py`): one passing baseline plus one failing case for each rule above. A test also imports `production.py` in a subprocess with a bad env and expects a non-zero exit.
- `urls.py` mounts no admin (criterion 3). A test asserts that `/admin/` returns 404 with the envelope.

### 6.3 Endpoints and cross-cutting behaviour (criteria 4–6) — REVIEW
| Method + path | Permission | Response | Errors |
|---|---|---|---|
| `GET/HEAD /health/live` | public (explicit `AllowAny`, `authentication_classes=[]`; threat-model entry) | 200 `{"status":"ok"}`, no DB access | 405 `method_not_allowed` |
| `GET/HEAD /health/ready` | same | 200 `{"status":"ok"}` after `SELECT 1` on `default` | 503 `not_ready` (generic message; exception class logged, no detail) |
| any unknown path | — | — | 404 `not_found` envelope (`handler404`); 500 `server_error` (`handler500`, generic) |
| any unsafe method failing CSRF | — | — | 403 `csrf_failed` envelope |
- Every error response uses the `api.md` envelope with `request_id`.
- Request-ID middleware runs first. It always generates a UUID4 server-side; an inbound `X-Request-ID` is ignored until a trusted proxy exists. It stores the ID in a contextvar and returns it in the `X-Request-ID` response header.
- The API security-headers middleware adds `Cache-Control: no-store` (TM-45) and `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` to every backend response. The SPA's CSP belongs to whatever serves it (0008 / Phase 10).
- Logging uses one JSON line per record: `ts, level, logger, message, request_id, tenant_id, membership_id` (the last two are null until 0004/0005), plus `extra` and `exc_type`. The redaction filter walks `args`/`extra` recursively. It replaces the value of any key that case-insensitively contains `password, passwd, secret, token, key, authorization, cookie, session, csrf, pin, otp, credential` with `"[REDACTED]"`. Tests cover nested dicts, lists and `%`-args. Value-pattern redaction and personal-data fields are a follow-up (0005). Request bodies are never logged.
- Tests for each row of the table above, plus the request-ID header, JSON log shape, and redaction.

### 6.4 Dependencies (versions are ranges; the lockfiles pin exact versions) — REVIEW (new deps pass the audit)
- **Backend runtime:** `django>=5.2,<5.3` (LTS), `djangorestframework>=3.16,<4`, `psycopg[binary]>=3.2,<4` (whether production uses the binary wheel or a source build is decided in Phase 10).
- **Backend dev group:** `pytest>=8,<9`, `pytest-django>=4.9,<5`, `ruff` (latest at implementation, exact pin), `mypy>=1.15,<2`, `django-stubs[compatible-mypy]>=5.2,<6`, `djangorestframework-stubs[compatible-mypy]>=3.16,<4`.
- **Backend tooling config:** `requires-python=">=3.12"`. ruff: `line-length=100`, rules `E,W,F,I,B,UP,S,DJ,SIM,RUF,N`, with `S101` ignored in tests. mypy: `strict=true` from the start (the codebase is empty) with the django-stubs plugin on `config.settings.test`. pytest: `DJANGO_SETTINGS_MODULE=config.settings.test`, `--strict-markers`, **migrations are not disabled** (RLS will live in migrations).
- **Frontend dependencies:** `react@^19`, `react-dom@^19`, `react-router@^7`, `@tanstack/react-query@^5`.
- **Frontend devDependencies:** `typescript` (current stable major, `strict` + `noUncheckedIndexedAccess`), `vite`, `@vitejs/plugin-react`, `vite-plugin-pwa@^1`, `tailwindcss@^4` + `@tailwindcss/vite`, `vitest`, `jsdom`, `@testing-library/react@^16`, `@testing-library/jest-dom@^6`, `@testing-library/user-event@^14`, `eslint@^9`, `@eslint/js`, `typescript-eslint@^8`, `eslint-plugin-react-hooks`, `prettier@^3`. Engineers take the current stable major of each unpinned tool and record it in 7.
- **Deliberately excluded:** django-environ, structlog, python-json-logger, dj-database-url, django-cors-headers, gunicorn, celery/redis, whitenoise, axios, eslint-plugin-react.
- **ESLint:** `no-restricted-syntax` bans the `dangerouslySetInnerHTML` JSX attribute, and `no-restricted-globals` bans `localStorage`/`sessionStorage`. A reviewed preferences module may be exempted later.
- **PWA:** manifest with name, `display: standalone`, and 192/512 plus maskable placeholder icons. Workbox precaches the app shell only. `navigateFallbackDenylist: [/^\/api\//, /^\/health\//]` and no runtime caching of `/api/` (TM-45).
- **API client:** `credentials: "same-origin"`. On POST/PUT/PATCH/DELETE it reads the CSRF cookie (`rms_csrf` when `import.meta.env.DEV`, otherwise `__Host-rms_csrf`) and sends it as `X-CSRFToken`. It parses the envelope into `ApiError{status, code, message, fields, requestId}`. A network failure becomes `code: "network_error"`. The 401 hook is a no-op stub until 0008. Vite `server.proxy` sends `/api` and `/health` to `http://127.0.0.1:8000` with the Host header preserved, so dev is same-origin like production (C6-1).
- **Shell:** header, main landing text and a safe-area-aware layout at 360px. Strings come from `i18n/messages.ts`. Vitest covers the shell render and the client (envelope parsing, CSRF header only on unsafe methods, network error).

### 6.5 Local Postgres and DB roles — REVIEW (data-engineer names/timeouts, security-engineer)
- **`compose.yaml` service `db`:** image `postgres:16` (digest pin: follow-up via Dependabot). Port `127.0.0.1:5432:5432`, never all interfaces. Named volume. `pg_isready` healthcheck. `scripts/db/bootstrap.sh` mounted as `/docker-entrypoint-initdb.d/10-bootstrap.sh`. Variables come from the root env file. No other services.
- **`bootstrap.sh`** runs as the container superuser through `psql -v ON_ERROR_STOP=1`. Names are passed with `-v` and quoted as `:"name"`, passwords as `:'pw'`, so no SQL is string-built. It is idempotent and does the following:
  1. `rms_migrator`: LOGIN, NOSUPERUSER, NOCREATEROLE, NOBYPASSRLS, **CREATEDB (local/CI only, needed to create the test DB)**.
  2. `rms_app`: LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOBYPASSRLS, NOINHERIT, member of nothing. `ALTER ROLE … SET statement_timeout='15s'`, `idle_in_transaction_session_timeout='30s'` (dev values, C3-10; data-engineer sets the real ones).
  3. Template DB `rms_template` owned by `rms_migrator`. Inside it: `public` schema owned by `rms_migrator`; `REVOKE ALL ON SCHEMA public FROM PUBLIC`; `GRANT USAGE ON SCHEMA public TO rms_app`; `ALTER DEFAULT PRIVILEGES FOR ROLE rms_migrator IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO rms_app` (plus `USAGE,SELECT ON SEQUENCES`). Default privileges are stored per database, which is why a template is used.
  4. `rms` (the dev DB) is created from `rms_template`, owned by `rms_migrator`. `REVOKE ALL ON DATABASE … FROM PUBLIC`, then `GRANT CONNECT` to both roles.
- `rms_scheduler` is **not** created until a scheduler exists (C3-8). Unused credentials are not provisioned. Per-table REVOKEs (no UPDATE on `tenant_id`, audit tables INSERT/SELECT only) happen in the migrations of 0004/0007.
- **Test DB (C3-7):** in `test.py`, alias `migrator` has `TEST={"NAME":"test_rms","TEMPLATE":"rms_template"}`, and `default` (app role) has `TEST={"MIRROR":"migrator"}`. Django then creates and migrates `test_rms` as the migrator, and tests connect to it as `rms_app`. **Footgun:** Django applies the mirror even when the mirror target was not set up, which would leave `default` pointing at the dev DB `rms`. So `conftest.py` overrides `django_db_setup` to always set up the aliases `{"default","migrator"}`. Tests declare only `default`.
- **Guard tests (in 0003):** `current_database()=='test_rms'`; `current_user` is not superuser and has no BYPASSRLS; `pg_has_role(current_user, <migrator>, 'MEMBER')` is false; the app role cannot `CREATE TABLE` in `public`. If MIRROR proves unworkable, the engineer reports `BLOCKED` with a fallback proposal (a custom `django_db_setup` that creates and migrates through the migrator connection). Tests must not quietly connect as the migrator.

### 6.6 Env and Makefile (criteria 8–9) — AUTO
- **Env example** (placeholders only, e.g. `change-me`): `POSTGRES_PASSWORD, DB_HOST=127.0.0.1, DB_PORT=5432, DB_NAME=rms, DB_APP_USER=rms_app, DB_APP_PASSWORD, DB_MIGRATOR_USER=rms_migrator, DB_MIGRATOR_PASSWORD, DJANGO_SETTINGS_MODULE=config.settings.local, DJANGO_SECRET_KEY, DJANGO_DEBUG=true, DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1, DJANGO_CSRF_TRUSTED_ORIGINS=, DJANGO_SECURE_PROXY_SSL_HEADER=, LOG_LEVEL=INFO`.
- **Env loading:** backend commands run through `uv run --env-file <root env file> …`, so there is no dotenv dependency. Agents never read the env file.
- **Makefile targets** (`.PHONY`; each runs the per-side sub-targets `*-backend`/`*-frontend` that CI calls):
  - `setup`: `init-env`, `uv sync --frozen`, `npm ci`, `up`, `migrate`
  - `up`: `docker compose up -d --wait db`; `down`: `docker compose down` (keeps the volume)
  - `migrate`: `manage.py migrate --database migrator`
  - `run`: `make -j2 run-backend run-frontend` (`runserver 127.0.0.1:8000`, `vite`)
  - `lint`: `ruff check`, `ruff format --check`, `eslint .`, `prettier --check .`
  - `fmt`: `ruff format`, `ruff check --fix`, `prettier --write .`, `eslint --fix .`
  - `typecheck`: `mypy .`, `tsc -b --noEmit`
  - `test`: `pytest`, `vitest run`
  - `migrations-check`: `manage.py makemigrations --check --dry-run`
  - `audit`: `uv export --frozen --format requirements-txt --no-emit-project` to a temp file, then `uvx pip-audit --strict --require-hashes --disable-pip -r <file>`, and `npm audit --omit=dev`
  - `secrets`: the gitleaks Docker image (pinned tag) in `git` mode over the repo, plus `--pre-commit --staged` locally
  - `check`: lint, typecheck, migrations-check, test, audit, secrets, `build-frontend`

### 6.7 CI — `.github/workflows/ci.yml` — REVIEW
- **Trigger and job settings:** `push` + `pull_request`. `permissions: contents: read`. Concurrency cancels superseded runs. Third-party actions are pinned by commit SHA. `timeout-minutes` set on each job.
- **Jobs:**
  1. `backend`: checkout; `astral-sh/setup-uv`; `uv sync --frozen`; generate the env file with `scripts/dev/init-env.sh` (random values per run); `make up`; `make lint-backend typecheck-backend migrations-check test-backend`.
  2. `frontend`: checkout; `actions/setup-node` (`node-version-file: frontend/.nvmrc`, npm cache); `npm ci`; `make lint-frontend typecheck-frontend test-frontend build-frontend`.
  3. `audit`: setup-uv + setup-node; `make audit`.
  4. `secrets`: checkout with `fetch-depth: 0`; gitleaks Docker image (pinned). The `gitleaks-action` is avoided because it needs a licence for organisations.
- **`.github/dependabot.yml`:** weekly updates for `uv` (backend), `npm` (frontend), `github-actions` and `docker` (security control 18).
- **Deferred:** the migration backward check (first real migrations, 0004); the RLS catalog check (0004); the runtime-env check that migrator credentials are absent (R16, 0004/Phase 10); Playwright (0008); pre-commit hooks (follow-up).

### 6.8 Supply-chain notes for security review
`npm audit --omit=dev` and `pip-audit --strict` fail on any severity (no allow-list yet). Adding an allow-list entry would be a `docs/risks.md` acceptance. Lockfiles are committed. CI installs only with `--frozen` / `npm ci`.

### 6.9 `.claude/rules` globs (criterion 11)
The layout matches the existing globs: `backend/**`, `frontend/**`, `backend/**/migrations/**`, and `frontend/**/api/**` (matches `src/lib/api/`). **No change is required.** Optional proposal, `APPROVAL`, non-blocking: add `scripts/db/**` to `.claude/rules/database.md` `paths:`, so that the role-bootstrap script is covered by the database rules (it is `.sh`, so `**/*.sql` does not match it).

## 7. Implementation

### Frontend
*(frontend-engineer, 2026-10-01.)*
- **Files:** everything under `frontend/`: `package.json`, `package-lock.json`, `.nvmrc` (24), `.prettierrc.json`, `.prettierignore`, `eslint.config.js`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `vite.config.ts`, `index.html`, `config/pwa.ts`, `config/config.test.ts`, `public/icons/{favicon.svg,icon-192.png,icon-512.png,icon-maskable-512.png}`, `src/main.tsx`, `src/app/{App,AppShell,pages,providers,router}.tsx`, `src/app/AppShell.test.tsx`, `src/lib/api/{client,errors}.ts`, `src/lib/api/{client,errors}.test.ts`, `src/i18n/messages.ts`, `src/styles/index.css`, `src/test/setup.ts`. Also `docs/conventions/frontend.md` (criterion 12).
- **Versions locked** (current stable major, except where 6.4 fixes a major): react/react-dom 19.3.0, react-router 7.18.4 (6.4 `^7`; 8.x exists), @tanstack/react-query 5.104.0, typescript 6.0.3, vite 8.3.1, @vitejs/plugin-react 6.1.1, vite-plugin-pwa 1.3.0, tailwindcss/@tailwindcss/vite 4.3.3, vitest 5.0.3, jsdom 30.1.1, @testing-library/react 16.3.3, @testing-library/dom 10.4.2, @testing-library/jest-dom 6.9.1 (6.4 `^6`; 7.x exists), @testing-library/user-event 14.6.7, eslint/@eslint/js 9.39.5 (6.4 `^9`; 10.x exists), typescript-eslint 8.71.0, eslint-plugin-react-hooks 7.1.1, prettier 3.9.9, globals 17.13.0, @types/react(-dom) 19.3.0, @types/node 24.19.0.
- **Deviations from 6.1/6.4:**
  - TypeScript is `~6.0.3`, not 7.x, because typescript-eslint 8 declares the peer range `typescript >=4.8.4 <6.1.0`. — REVIEW
  - Added devDependencies not listed in 6.4: `@testing-library/dom` (a required peer of `@testing-library/react` 16), `globals` (ESLint flat-config globals) and `@types/node` (TypeScript 6 defaults `types` to `[]`, and `vite.config.ts` uses `node:url`). — REVIEW
  - Added `src/app/pages.tsx` (home, not-found and route-error pages) and `config/pwa.ts` (PWA options in their own module so NT3-12 can test them). `components/ui/` is not created yet, because the shell needs no shared primitive. — AUTO
- **SC controls:**
  - SC-40: `resolveApiPath` and `ApiPathError` throw before `fetch` (tests in `client.test.ts`). `redirect: "error"` is added so a redirect cannot carry the request elsewhere.
  - SC-41: `envDir` is set explicitly to `frontend/`, and `envPrefix` is `VITE_` (`config/config.test.ts`). The CI gitleaks `dir` scan of `frontend/dist` belongs to the CI files (backend-engineer). frontend-engineer ran it once locally on 2026-10-01 (gitleaks v8.28.0 image, `dir --redact`): no leaks found.
  - SC-42: `server.host: "localhost"` is explicit, with `fs.strict: true` and `strictPort` (tested). Preview is also loopback.
  - SC-34 recommendation: `npm ci --ignore-scripts` followed by build and test passes, so CI can use it.
- **Decisions:**
  - `registerType: "prompt"` with no prompt UI: a new service worker waits until all tabs close, so an update never reloads mid-task. The update prompt is left to 0008. — REVIEW
  - Query retry policy: network errors and 5xx only, at most 2 retries (3 attempts); mutations are never auto-retried. — AUTO
  - A non-envelope error body is never shown to the user; it becomes `unexpected_response` with a catalog message. — AUTO
  - A caller-supplied `X-CSRFToken` is always discarded. — AUTO
  - The placeholder palette is teal `#0f766e` with white text (contrast about 5.5:1, AA). Branding is a human decision. — REVIEW
- **Not built (out of scope / 0008):** loading, empty, offline, success and permission-denied states. The shell has no data view or mutation, so only not-found and route-error exist. Also left to 0008: the in-app update prompt, the 401 re-auth flow, tenant routes, Playwright, react-hook-form/zod.
- **Round-trip 1 (frontend)** *(frontend-engineer, 2026-10-01; fixes from section 10):*
  - m2: the code is unchanged (`shouldRetryQuery` allows 2 retries). The wording is corrected to "at most 2 retries (3 attempts)" in `docs/conventions/frontend.md:21` and in the Decisions list above. — AUTO
  - m5: added `AppShell.test.tsx` "shows the route-error page without error details when a child route throws". It reuses the real root route's `element` and `errorElement`, adds a child that throws a canary message, and asserts `role="alert"`, the `routeError.title` h1, a home link to `/`, and that the canary text is absent. Mutation check: with `errorElement: undefined` (the router's default error UI) the test fails. — AUTO
  - n4: the `ApiPathError` comment in `frontend/src/lib/api/client.ts:21` now says `resolveApiPath` throws it and `apiRequest` rejects with it. — AUTO
  - Re-run in `frontend/`: `npm run lint` exit 0 (eslint clean; Prettier "All matched files use Prettier code style!"), `npm run typecheck` exit 0, `npm run test` 4 files / 73 tests passed (was 72), `npm run build` exit 0 (PWA generateSW, 14 precache entries).

### Backend
*(backend-engineer, 2026-10-01.)*
- **Files:**
  - `backend/`: `pyproject.toml`, `uv.lock`, `.python-version` (3.12), `manage.py`, `conftest.py`.
  - `backend/config/`: `env.py`, `validation.py`, `urls.py`, `wsgi.py`, `settings/{base,local,test,production}.py`, and `tests/{db_guards,test_db_guards,test_env,test_init_env,test_routes,test_validation}.py`.
  - `backend/rms/core/`: `apps.py`, `context.py`, `middleware.py`, `logging.py`, `health.py`, `api/{errors,permissions}.py`, and `tests/{views,urls,test_errors,test_headers,test_health,test_logging,test_request_id}.py`.
  - Root: `scripts/dev/init-env.sh`, `scripts/db/bootstrap.sh`, `scripts/ci/{db-check,check-workflows}.sh`, `compose.yaml`, `.env.example`, `Makefile`, `.github/workflows/ci.yml`, `.github/dependabot.yml`, `.github/zizmor.yml`.
  - Docs: `docs/conventions/backend.md` (criterion 12), `docs/process/testing-strategy.md`, `docs/process/operations.md`, `README.md`.
- **Versions locked:**
  - Runtime: Django 5.2.17, djangorestframework 3.18.1, psycopg[binary] 3.3.6.
  - Dev: pytest 9.1.1, pytest-django 4.14.0, ruff 0.16.9, mypy 1.19.1, django-stubs 5.2.9, djangorestframework-stubs 3.16.9.
  - Tools: uv 0.11.10, pip-audit 2.10.1, zizmor 1.30.1, gitleaks v8.30.1.
  - Actions: `actions/checkout` v7.0.1 `3d3c42e5aac5ba805825da76410c181273ba90b1`, `actions/setup-node` v7.0.0 `820762786026740c76f36085b0efc47a31fe5020`, `astral-sh/setup-uv` v10.2.0 `c18668ad3cf93ea998bef934396af7bb5c839dc7`. Resolved with `git ls-remote`; all three are lightweight tags pointing at commits, and the input names were checked against each `action.yml` at that SHA.
  - Images: `postgres:16@sha256:1a6ab3f5345eb6dbe04a1349529caabdb0ab09293a09590fad07b2246bfa4b54` (PostgreSQL 16.15) and `ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`. Both come from `docker pull` + `docker inspect`.
- **MIRROR re-check against Django 5.2.17** (the 5.2 assumption is now verified):
  - `setup_databases` still applies every mirror unconditionally (`django/test/utils.py:226-230`).
  - `set_as_test_mirror` copies only `NAME` (`django/db/backends/base/creation.py`).
  - Flush, fixtures and sequence reset still skip mirrors (`django/test/testcases.py:1152,1169,1200,1256,1417,1472`), so SC-29 stands.
  - **New:** `get_unique_databases_and_mirrors` makes a non-default alias with a different signature depend on `default`. Because `default` is a mirror, setup fails with "Circular dependency in TEST[DEPENDENCIES]". So `migrator` sets `TEST["DEPENDENCIES"]=[]`. MIRROR is workable; no BLOCKED fallback was needed.
- **Decisions and deviations:**
  - `pytest>=9.0.3,<10` instead of 6.4's `>=8,<9`. pip-audit flags pytest 8.4.2 (PYSEC-2026-1845, fixed in 9.0.3). This is a range change to a listed dev dependency, not a new one. Three tests were adapted to pytest 9, which also captures non-propagating loggers (`_pytest/logging.py:356`). — REVIEW
  - `uv sync --locked` (SC-34) everywhere, `make setup` included, instead of 6.6's `--frozen`. All `make` targets use `uv run --locked`. — AUTO (section 5 wins)
  - Production sets `SILENCED_SYSTEM_CHECKS = ["security.W021"]` (HSTS preload not set). SC-07's `--fail-level WARNING` and 6.2's "preload stays off" otherwise conflict. With silencing removed, W021 is the only deploy-check message (verified). — REVIEW (security)
  - SC-03 and NT3-03 disagree on `"False "`. SC-03 strips before matching, so `"False "` parses as `false`. NT3-03 lists it as "raise". I followed SC-03; `"no"`, `"off"`, `"yes"`, `"on"` raise. The threat (T3-03, value read as truthy) cannot happen either way. — REVIEW
  - The `db` service also receives `DB_NAME` (not secret; needed to name the dev DB), in addition to SC-28's list. — REVIEW
  - `POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256` in addition to `POSTGRES_HOST_AUTH_METHOD`. The container-local Unix socket keeps the image's `trust` default, which bootstrap and `db-check` use from inside the container. — REVIEW (data-engineer, security)
  - The compose healthcheck uses TCP (`pg_isready -h 127.0.0.1`). During initdb the temporary server listens on the socket only, so `up --wait` returns only after bootstrap has finished. — AUTO
  - bootstrap.sh adds `\set VERBOSITY terse` and `SHOW_CONTEXT never`. Verified: with default verbosity psql echoes the failing statement text, password included, to stderr (the compose log). With terse it does not, and the server log has no copy either (canary test). It also revokes any role membership of the app role, so "member of nothing" holds on re-run. — AUTO
  - `ApiSecurityHeadersMiddleware` sets `nosniff`, `X-Frame-Options` and `Referrer-Policy` itself, besides `Cache-Control` and the CSP. A `DisallowedHost` raised inside an inner middleware skips that middleware's response hook, so this makes SC-16 independent of middleware order. — AUTO
  - `RequestIDMiddleware` calls Django's `log_response` for 4xx/5xx inside the request context. Django otherwise logs them after the middleware chain returns, with `request_id: null`. — AUTO
  - The health views set `http_method_names = ["get", "head"]`, so `OPTIONS` returns 405 instead of DRF's view metadata. — AUTO
  - The JSON formatter adds an `exc` field (the formatted traceback) beside `exc_type` when a record has `exc_info`. The SC-19c secret scrub covers it. The readiness check logs only `error_class`, never `exc_info`. — REVIEW (security)
  - The known-secret scrub replaces the raw and the JSON-escaped form of each value. It has no minimum length, so very short dev passwords over-redact. Generated values are 48 or more characters. — AUTO
  - `init-env.sh`: `openssl rand -hex`. `DJANGO_SECRET_KEY` is 96 characters, DB passwords 48. Paths can be overridden with `RMS_ENV_EXAMPLE`/`RMS_ENV_FILE` for NT3-26. The example's header comment avoids the placeholder literal, so the "no placeholder left" check applies to the whole file. — AUTO
  - shellcheck (SC-22 recommendation): `make lint-shell` skips with a notice when shellcheck is missing locally. CI sets `REQUIRE_SHELLCHECK=1`, so it cannot skip there. — REVIEW
  - Workflow linter: zizmor 1.30.1 with `--offline` and `.github/zizmor.yml` (`"*": hash-pin`), plus `scripts/ci/check-workflows.sh` for what zizmor does not check (`issue_comment`/`workflow_dispatch` triggers, `secrets.*`, `persist-credentials: true`, job-level permissions, version comments, env dumps). Offline mode skips zizmor's online audits (impostor-commit, known-vulnerable-actions), because the workflow holds no token. — REVIEW (security)
  - gitleaks runs with `--verbose` as well as `--redact`, so CI shows file, line and rule; the secret appears as `REDACTED`. — REVIEW (security)
  - `setup-uv` uses `enable-cache: false` (no cache-poisoning surface). Jobs have `name:` for SC-38 required checks. CI masks the generated values of `*PASSWORD` and `DJANGO_SECRET_KEY` only. — AUTO
  - Make targets added beyond 6.6: `install*`, `db-check`, `db-bootstrap`, `deploy-check`, `secrets-staged`, `secrets-dist`, `workflow-lint`, `help`, and `PYTEST_ARGS`. `make check` includes `deploy-check`. — AUTO
  - Frontend contract confirmed. The Makefile and CI call `npm ci --ignore-scripts`, `npm run lint|typecheck|test|build`; `make run`/`fmt` use `npm run dev|format`. Cookie names match the frontend (`rms_csrf` local, `__Host-rms_csrf` production; both asserted in `test_validation.py`). The Vite proxy with Host preserved works with local `ALLOWED_HOSTS` and Django's Origin check without `CSRF_TRUSTED_ORIGINS`. — AUTO
- **SC → implementation → evidence:**
  - SC-01, 03, 05 (list reader), 06: `config/env.py`; `test_env.py`.
  - SC-02, 04, 25c: settings modules; `test_validation.py` (subprocess imports).
  - 6.2 rules 1-6 and SC-05 rules 7-12: `config/validation.py`; `test_validation.py` (baseline plus 34 failing cases).
  - SC-07: `make deploy-check` (positive and `DJANGO_DEBUG=true` negative).
  - SC-10: `base.py` `connect_timeout` 5, `health.py`; `test_health.py`.
  - SC-11, 14: `test_routes.py` (scan plus self-test).
  - SC-13, 15: `api/errors.py`; `test_errors.py`.
  - SC-16: `middleware.py`; `test_headers.py` (200/404/405/500/400/403 CSRF/403 DenyAll).
  - SC-18: `middleware.py`, `context.py`; `test_request_id.py`.
  - SC-19, 20: `rms/core/logging.py`; `test_logging.py`.
  - SC-22: `bootstrap.sh`; `db-check.sh` re-run (NT3-22).
  - SC-23: `compose.yaml`; `db-check.sh`.
  - SC-24, 25a/b: `conftest.py`, `db_guards.py`; `test_db_guards.py`.
  - SC-26, 27: `init-env.sh`, `.env.example`; `test_init_env.py`, CI clean-tree step.
  - SC-28: `compose.yaml`.
  - SC-30..33, 37: `ci.yml`; `make workflow-lint`.
  - SC-34, 35: `Makefile` `install-*`/`audit-*`.
  - SC-36: `Makefile` `secrets*`.
  - SC-39: `dependabot.yml`. The `docker-compose` ecosystem and `cooldown` were checked against the vendored GitHub schema with check-jsonschema 0.38.2, run as a one-off tool, not added to the project.
  - SC-41: `make secrets-dist`.
  - SC-38 is human; documented in `operations.md`.
- **One-time verifications (input for section 8; not committed):**
  - NT3-25: with the `django_db_setup` override disabled and only `default` declared, both aliases pointed at the dev DB. The session guard aborted with exit 3 and "no tests ran". With `test_db_guards.py` in the run, it aborted on missing lock-down (TEMP). The override was then restored, and `diff` confirmed it byte-identical.
  - NT3-30: on a bad workflow copy (pull_request_target, `contents: write`, `persist-credentials: true`, a tag-pinned action, `${{ github.event... }}` in `run:`, an artifact upload of `.`), zizmor exited 14 and the policy script exited 1, each naming the injected faults. The real workflow exits 0.
  - NT3-36: gitleaks `dir` on a temp dir holding a freshly generated throwaway ed25519 key exited 1 with `RuleID: private-key`, `Secret: REDACTED`, and no key header in the output. The key was deleted.
  - bootstrap echo: under the bootstrap settings, a failing `ALTER ROLE … PASSWORD` with a canary printed only the terse error. The canary was absent from stderr and from the server log. Without terse, a syntax error echoed it.
- **Verification (2026-10-01, local):**
  - `make init-env` created the env file. A second run left it unchanged, and `git status` does not list it.
  - `make install` passed; `make up` brought `rms-db-1` to healthy, with the port `127.0.0.1:5432`.
  - `make db-check` passed all 3 assertions.
  - `make lint-backend`: ruff check and format check passed (37 files).
  - shellcheck 0.11.0 (`koalaman/shellcheck` image, one-off) on the four scripts: exit 0.
  - `make typecheck-backend`: no issues in 37 files.
  - `make migrations-check`: "No changes detected".
  - `make test-backend`: 215 passed.
  - `make deploy-check`: "no issues (1 silenced)", and the debug negative was refused.
  - `make audit`: pip-audit found no known vulnerabilities; both npm audits found 0.
  - `make workflow-lint`: zizmor "No findings" and the policy script OK.
  - `make secrets`: 0 commits scanned. The branch has no commits yet, so a `dir` scan over a copy of every non-ignored file (169 files) was also run: no leaks.
  - `make secrets-dist`: no leaks.
  - Frontend via make (`lint/typecheck/test/build`): exit 0, 72 tests.
  - `make check`: exit 0.
  - **Not run:** `make migrate` against the dev DB. `manage.py migrate` is on the project's permission ask-list, and running it through make would skip that prompt. The migrate path is exercised by test-DB creation as the migrator. CI was not run on GitHub, because no repository exists.
- **Follow-ups (not in scope):**
  1. The default privileges grant the app role DML on every migrator-created table, `django_migrations` included. The app role can therefore rewrite migration history. Revoke that in 0004 with the per-table REVOKEs. (data-engineer)
  2. The stock `postgres` database keeps PUBLIC `CONNECT`/`TEMP`, so the app role can connect to it and create temp tables there. Consider `REVOKE ALL ON DATABASE postgres FROM PUBLIC` plus `CONNECT` for the migrator, which Django uses there to create the test DB. (data-engineer)
  3. The `tenancy.md` role names are not filled in, pending data-engineer confirmation. `CHANGELOG.md` was not updated (orchestrator).
  4. **F5 (security review, low):** `uvx pip-audit==…` and `uvx zizmor==…` pin only the top-level tool; their transitive dependencies resolve fresh on each run. Pin them with `uvx --exclude-newer <date>` or a hashed tool requirements file that Dependabot updates. Not done in 0003 (not trivial: it needs an update path for the date or the hashes). (backend-engineer, next CI change)

#### Round-trip 1 (backend)
*(backend-engineer, 2026-10-01; fixes for 9.3 F1–F4, F6 and 10 m1, m3, m4, n1, n3.)*
- **F1 = m4 (`Makefile` `deploy-check`).** The `DJANGO_DEBUG=true` negative now captures stderr in a temp file and passes only if it contains `DJANGO_DEBUG must be false` (the value-free message from `config/validation.py:80`). Any other failure fails the target, with a hint to re-run by hand; the stderr is not printed. Proven with a scratch Makefile copy whose needle was altered: the target failed with that hint. — AUTO
- **m1 (`Makefile`, `README.md`, `docs/process/operations.md`).** `check` now also runs `secrets-dist` (after `build-frontend`) and `workflow-lint`. `db-check` stays out. The target list is in `CHECK_TARGETS`, so `make help` still shows `check`. The help text, README and operations.md now say "all checks CI runs except the DB assertions (`make db-check`); shellcheck is skipped if not installed". — AUTO
- **m3 (`backend/rms/core/api/errors.py`).** `exception_handler` calls `rest_framework.views.set_rollback()` before returning the error response, as DRF's own handler does. New test-only view `RollbackProbeView` (`rms/core/tests/views.py`, route `t/rollback/<outcome>`) writes transaction-local state (`set_config('rms.rollback_probe', …, true)`; the app role has no table to write yet), then succeeds or raises a handled 400/404. Tests in `test_errors.py`, with `ATOMIC_REQUESTS` turned on for `default` by a fixture:
  - `test_successful_request_commits_probe` (control: the state survives a 200);
  - `test_handled_4xx_rolls_back_request_transaction[validation|not-found]`;
  - `test_exception_handler_marks_atomic_block_for_rollback`.
  With the call removed, the last three fail (checked, then restored). `test_routes.py` self-test now expects the new test route to be flagged too. Fact: `set_rollback()` acts only on `ATOMIC_REQUESTS` aliases (DRF `views.py:66-69`), and `ATOMIC_REQUESTS` is off in every settings module today. Whether 0004/0005 turn it on is their design decision; `backend.md` documents both cases. — REVIEW (code-reviewer: test via a transaction-local GUC rather than a table)
- **F2 (`scripts/ci/test-check-workflows.sh`, `scripts/ci/testdata/*.yml`, `Makefile` `workflow-lint`).** 26 bad-workflow fixtures, each with exactly one fault and its expected message on line 1 (`# expect: …`). They live only under `scripts/ci/testdata/`, never under `.github/workflows/`. The self-test requires, for each fixture, exit 1, the expected message, and no other `check-workflows:` failure. `make workflow-lint` runs zizmor, then the policy script on the real workflow (exit 0), then the self-test. The rules covered: each forbidden trigger, permissions missing / raised to write / set per job, `secrets.*`, `persist-credentials` true / missing, tag-pinned / uncommented action, `${{ }}` inline and in a `run: |` block, artifact upload, each env-dump form, env-file reads, `docker compose config`. Mutation check on a scratch copy: disabling the persist-credentials count, the env-dump regex or the inline-trigger regex each made the self-test fail with exit 1. The upload-artifact fixture uses an all-zero placeholder SHA, labelled as such, so that no hand-typed SHA looks like a real pin. — AUTO
- **SC-30 gap found while writing the F2 fixtures (`check-workflows.sh`).** The trigger regex matched only block form; `on: workflow_dispatch`, `on: [push, issue_comment]` and `on: {…: {}}` passed (verified: `on: [push, workflow_dispatch]` gave `OK`). zizmor's dangerous-triggers audit covers only `pull_request_target`/`workflow_run`. The regex now also matches a trigger name as a whole word on the `on:` line; three fixtures cover it. This tightens an existing control and loosens nothing. — REVIEW (security-engineer)
- **F3 (`check-workflows.sh` SC-37).** The env-dump pattern now also matches bare `set`, `export`, `declare`, `typeset`, and `export -p`, `declare -p|-x`, `typeset -p`, `compgen -v|-e`, each ending the command (line end, `|`, `;`, `&`, `>`, `)`), so `set -euo pipefail` passes. A second pattern matches a printing command (`cat`, `tac`, `nl`, `less`, `more`, `head`, `tail`, `bat`, `strings`, `base64`, `xxd`, `od`) whose arguments name a `.env` file; `.env.example` and the mask step's `done < .env` redirect do not match. Fixtures: `env-dump-{env,printenv,set,export-p,declare-p,compgen-v}`, `env-read-cat`, `env-read-tail-quoted`. Known limit (line-based tripwire): a step name or `echo` ending in the word `env` or `set` is a false positive; the real workflow has none. — AUTO
- **F4 (`Makefile`).** `GITLEAKS_RUN` adds `--network none`; `secrets`/`secrets-staged` keep the read-only repo mount. `secrets-dist` mounts only `frontend/dist` (read-only, as `/dist`), and first checks that the directory exists, so docker cannot create a missing bind-mount source. — AUTO
- **F6 (`docs/process/operations.md`).** New CI bullet: every change to a `uses:` SHA, Dependabot PRs included, needs an impostor-commit check before merge, either an online `zizmor` run (read-only token) or `git ls-remote … refs/tags/<tag>` matching the pinned SHA, recorded by the reviewer in the PR. — AUTO (wording of the 9.4 ruling)
- **n1 (`backend/config/settings/test.py`).** Dropped the `TEST_DB_NAME.startswith("test_")` check on the constant. The `DB_NAME == TEST_DB_NAME` refusal stays, with the message "the test DB name must differ from DB_NAME" (`test_test_settings_refuse_dev_db_name` still asserts it). `backend.md` updated. — AUTO
- **n3 (`docs/conventions/backend.md`).** Corrected: importing `rest_framework.views` loads `rest_framework.schemas`, whose `generators.py:10` imports `django.contrib.admindocs.views`, which imports `django.contrib.admin` and `django.contrib.auth` modules. Verified by listing `sys.modules` after `import rest_framework.views`. The import is unconditional, because `views.py:18` imports `rest_framework.schemas`. — AUTO
- **Docs also updated:** `docs/process/testing-strategy.md` (the `secrets` job row names the self-test); operations.md command table (`secrets-dist`, `workflow-lint` self-test) and gitleaks bullet (`--network none`, dist-only mount).
- **Not changed:** `CHANGELOG.md` (m6, orchestrator); `frontend/` (m2, m5, n4); n2 (accepted as is by the reviewer); `.github/workflows/ci.yml` (it already runs `make workflow-lint` and `make secrets-dist`, which now include the new checks).
- **Verification (2026-10-01, local, `rms-db-1` healthy):**
  - `make check`: exit 0. ruff "All checks passed!", 37 files formatted; lint-shell skipped (shellcheck not installed); mypy no issues in 37 files; "No changes detected"; pytest 231 passed; Vitest 73 passed (4 files); deploy-check "no issues (1 silenced)" plus the debug refusal; pip-audit "No known vulnerabilities found"; both npm audits found 0; gitleaks history "0 commits scanned … no leaks found"; build OK; `secrets-dist` no leaks found; zizmor "No findings"; `check-workflows: OK (1)`; `test-check-workflows: OK (26 fixtures rejected as expected)`.
  - `make workflow-lint`: exit 0 (same three lines).
  - `make db-check`: exit 0: port bound to loopback, wrong-password TCP login rejected, bootstrap re-run idempotent.
  - shellcheck 0.11.0 (`koalaman/shellcheck:stable` image, one-off, `--network none`) on all five scripts: exit 0.

## 8. Testing
*(qa-engineer, gate 8, 2026-10-01. Every test listed below was read and checked against what it claims. "QA" marks tests added at this gate; all are test-only changes.)*

### 8.1 Acceptance criteria → tests
| # | Criterion | Evidence |
|---|-----------|----------|
| 1 | Django/DRF/uv project, settings split, env validation at startup | `config/tests/test_env.py` (all readers); `test_validation.py` subprocess imports of `local`, `test`, `production` (`test_production_imports_with_good_env`, `test_production_refuses_bad_env[*]`, `test_local_*`, `test_test_settings_*`); `uv sync --locked` / `uv run --locked` in `make check` |
| 2 | Production refuses DEBUG, weak key, empty/wildcard hosts, CORS wildcard + credentials | `test_validation.py::test_rule_fails[1-*,2-*,3-*,4-*]`, `test_debug_env_var_fails`, `test_production_refuses_bad_env[debug,wildcard,spaced-wildcard,empty-entry,weak-key]`, `test_production_requires_secret_key`; `make deploy-check` (positive + `DJANGO_DEBUG=true` negative) |
| 3 | Secure production defaults; proxy header only if configured; XFO DENY; no admin | **QA** `test_production_secure_defaults` (the values production actually has: secure/`__Host-` cookies, HSTS 1 y + subdomains, SSL redirect, `SECURE_PROXY_SSL_HEADER is None`, XFO `DENY`, no contrib apps, only W021 silenced); **QA** `test_production_proxy_header_only_when_configured`; `test_routes.py::test_admin_is_not_mounted`, `test_no_contrib_apps_installed`; `test_rule_fails[6-*,9-*]` |
| 4 | `/health/live`, `/health/ready`; no auth, no data | `rms/core/tests/test_health.py` (200 bodies, HEAD, 405 for 5 methods × 2 paths, trailing slash 404, 503 on DB down, connect timeout); `test_routes.py` (both are the only public routes, `[AllowAny]` + no auth) |
| 5 | Error envelope and request-ID middleware | `test_errors.py` (400 bad host, 400 parse, 400 validation with `fields`, 403 CSRF, 404, 405 + `Allow`, 406, 415, 500 × 2; `request_id` equals the header in every case); `test_request_id.py` |
| 6 | JSON logging with request ID; redaction filter | `test_logging.py` (line shape, 19 sensitive keys, nesting, `%`-args, no mutation, cycle/depth/raising repr, known-secret scrub, DB logger pinned); `test_request_id.py::test_request_log_line_carries_request_id`, `test_log_outside_request_has_null_request_id` |
| 7 | Frontend: TS strict, PWA manifest, Tailwind, Query, Router, 360 px shell, API client stub | `src/app/AppShell.test.tsx` (shell, skip link, touch targets, not-found); `config/config.test.ts` (manifest, SW denylist, Vite env/host); `src/lib/api/client.test.ts`, `errors.test.ts`; `tsc -b` in `make typecheck` and `make build-frontend`. **Weak:** jsdom does no layout, so "at 360 px" is only `window.innerWidth = 360`; a real viewport check needs Playwright (0008) |
| 8 | compose PostgreSQL 16; no secrets committed; env example placeholders only | `make db-check` (loopback port, wrong-password rejected, bootstrap idempotent); `test_init_env.py::test_example_has_placeholders_only`; `make secrets` (see 8.4: 0 commits, vacuous) and `make secrets-dist` |
| 9 | One command each: setup, run, lint, type-check, test | `Makefile` targets `setup`, `run`, `lint`, `typecheck`, `test`, `check`; `make check` run below. `setup`/`run` were not executed by QA (setup runs `migrate`) |
| 10 | CI: lint, types, tests on real PostgreSQL, pip-audit, npm audit, secret scan, migration check | `.github/workflows/ci.yml` read: all steps present. `make workflow-lint` exit 0. Not run on GitHub (no repository) |
| 11 | `.claude/rules` globs match the layout | Review: `backend/**`, `frontend/**`, `frontend/**/api/**`, `backend/**/migrations/**`, `scripts/db/**` (database.md) all match real paths. No test applies |
| 12 | Conventions docs finalised | Review: `docs/conventions/backend.md` "Django + DRF (ADR-0004, as built in change 0003)" and `frontend.md` "Stack (ADR-0004, as built in change 0003)"; no "If ADR-0004 is accepted" text remains. No test applies |

### 8.2 Required negative tests and checks (5.5) → evidence
| NT | Evidence | Verdict |
|----|----------|---------|
| NT3-01 | `test_env.py` canary per reader (bool, int, list, choice, proxy, local hosts; `require_*` have no value to echo); `test_validation.py::test_messages_never_contain_values` (rules 2, 3, 5, 8, 9, 12, plus **QA** rules 7, 8-path and 11 ×2), `test_malformed_debug_env_var_fails`, subprocess `CANARY not in stderr` | Covered. Rules 1, 4, 6 and 10 take booleans/ints only |
| NT3-02 | `test_local_requires_secret_key`, `test_production_requires_secret_key`, `test_test_settings_generate_a_key` (≥ 64), `test_no_settings_module_contains_a_literal_secret` | Covered; gitleaks part vacuous (8.4) |
| NT3-03 | `test_bool_rejects_anything_else[no,off,yes,on,…]`, `test_bool_true`, `test_bool_false`, `test_bool_unset_defaults_to_false`; **QA** `test_production_ignores_debug_false_lookalikes` | **Conflict, flagged, not decided:** `test_bool_false` asserts `"False "` → `false` (SC-03, strip first); NT3-03 says `"False "` → raise. See 8.5 Q1 |
| NT3-04 | `test_local_refuses_real_hostname`, `test_test_settings_refuse_real_hostname`, `test_local_hosts_rejects_others` | Covered |
| NT3-05 | `test_rule_fails[7-*,8-*,9-*,10-*,11-*,12-*]` (one or more per rule; **QA** `8-session-path` covers "either cookie path"); `" *"` and empty-entry via `test_list_*` and `test_production_refuses_bad_env[spaced-wildcard,empty-entry]` | Covered |
| NT3-06 | `test_proxy_header_valid/unset/malformed[7 cases]`; **QA** settings-level `test_production_secure_defaults` (unset → `None`) and `test_production_proxy_header_only_when_configured` | Covered |
| NT3-07 | `test_production_refuses_bad_env[debug]`, `test_production_imports_with_good_env`; `make deploy-check` both directions | Covered. **QA** `test_wsgi_defaults_to_production_and_fails_closed`, `test_wsgi_with_good_production_env_uses_production`, `test_manage_defaults_to_local` add T3-04 (6.1 defaults) |
| NT3-09 | `test_ready_503_when_db_unreachable` (exact envelope; no detail in body or JSON log line) | Covered |
| NT3-10 | `test_ready_returns_within_connect_timeout` (`slow`, runs by default) | Covered; measured 5.00 s against a 6 s limit in 3 of 3 runs |
| NT3-11 | `test_root_urlconf_has_no_open_routes`, self-test `test_scan_flags_unlisted_and_test_only_routes`, `test_root_urlconf_has_no_test_views`, `test_undeclared_drf_view_is_denied` | Covered |
| NT3-12 | `test_live_ok_without_db`, `test_ready_ok`, `test_ready_503_*` (`no-store`); `config.test.ts` denylist + no runtime caching | Covered |
| NT3-13 | `test_bad_host_is_400_envelope`, `test_malformed_json_is_generic_400`, `test_404_does_not_echo_path`, `test_csrf_failure_does_not_echo_origin`, **QA** `test_csrf_failure_does_not_echo_referer` (HTTPS Referer path, proven by the log), `test_500_is_generic`, `test_debug_is_off` | Covered (Referer was missing) |
| NT3-15 | `test_csrf_failure_without_token`, `test_csrf_middleware_is_installed`, control `test_csrf_passes_with_matching_cookie_and_header` | Covered |
| NT3-16 | `test_headers.py::test_security_headers[200,404,405,500,400-bad-host,403-csrf,403-deny-all]` | Covered |
| NT3-17 | `test_inbound_request_id_is_ignored[chosen,valid-uuid,crlf,10kB]`, `test_response_has_uuid4_request_id` | Covered |
| NT3-18 | `test_context_is_reset_after_request`, `…_after_raising_request`, `test_sequential_requests_get_different_ids`, `test_log_outside_request_has_null_request_id`, `test_500_envelope_request_id_matches_header` | Covered |
| NT3-19 | `test_debug_level_emits_no_sql`, `test_db_logger_pinned_at_warning`, `test_configured_secret_key_is_scrubbed` (message + traceback), `test_configured_db_password_is_scrubbed`, `test_request_extra_is_method_and_path_only`, `test_sensitive_extra_keys_are_redacted` (new keys) | Covered |
| NT3-20 | `test_self_referencing_dict`, `test_deep_nesting` (50), `test_object_with_raising_repr`, `test_raising_repr_in_message_args`, `test_redaction_error_marker`, `test_caller_objects_are_not_mutated` | Covered |
| NT3-21 | `test_newline_injection_stays_one_line` | Covered |
| NT3-22 | `scripts/ci/db-check.sh` step 3 (snapshot of role attributes, memberships, DB/schema ACLs, default privileges before and after a re-run); SC-22 by review | Covered; run by QA, passed |
| NT3-23 | `db-check.sh` steps 1–2 | Covered; run by QA, passed |
| NT3-24 | `test_db_guards.py` (11 tests) + the session guard `db_guards.database_guard_failures` | Covered |
| NT3-25 | `test_test_settings_refuse_remote_db_host`, `test_test_settings_refuse_dev_db_name`; abort-the-run: implementer's one-time check (7, "One-time verifications") | Covered; the one-time part was not repeated by QA (it means breaking `conftest.py`) |
| NT3-26 | `test_init_env.py` (mode 0600, no placeholder, same key set, values not in stdout/stderr, byte-identical re-run, no temp file left, missing example) | Covered |
| NT3-27 | CI step "Working tree is clean" | CI only; not run (no repository) |
| NT3-30 | `make workflow-lint` (exit 0 on the real workflow). **QA re-verified** on bad copies in the scratchpad: `pull_request_target`, `contents: write`, tag-pinned checkout and `${{ github.event… }}` in `run:` → zizmor exit 14 (dangerous-triggers, excessive-permissions, unpinned-uses, template-injection) and policy script exit 1. A checkout with `persist-credentials: true` and an `upload-artifact` of `.` → zizmor exit 0, policy script exit 1 | Covered. SC-31 (persisted credentials) and SC-37 (artifacts) rely on `check-workflows.sh` alone |
| NT3-36 | Implementer's one-time check (7) | Not repeated: generating a throwaway key was blocked by a permission hook |
| NT3-40 | `client.test.ts` rejects 17 paths, including `https://evil.test/x` and `//evil.test/x`, before `fetch`; CSRF header on POST/PUT/PATCH/DELETE only | Covered |
| NT3-41 | `make secrets-dist` | Covered; run by QA: no leaks |

Concurrency: the design names no race (5.6). Regression: no bug was fixed in this change. Two tenants: not applicable (no tenant data, 5.6).

### 8.3 Tests added at gate 8
- `backend/config/tests/test_validation.py`: rule case `8-session-path`; four NT3-01 canary cases (rules 7, 8, 11); `test_production_secure_defaults`, `test_production_proxy_header_only_when_configured`, `test_production_ignores_debug_false_lookalikes`, `test_wsgi_defaults_to_production_and_fails_closed`, `test_wsgi_with_good_production_env_uses_production`, `test_manage_defaults_to_local`.
- `backend/rms/core/tests/test_errors.py`: `test_csrf_failure_does_not_echo_referer`.
- No existing test was changed, skipped or loosened. No production code was changed.

### 8.4 Run results (2026-10-01, local, DB container `rms-db-1` already healthy)
- `make check`: **exit 0**.
  - ruff check passed and the format check passed (37 files); `lint-shell` was **skipped** (shellcheck is not installed locally; CI requires it); ESLint + Prettier passed.
  - mypy: no issues in 37 files; `tsc -b --noEmit` passed.
  - `makemigrations --check`: "No changes detected".
  - pytest: **227 passed** in 7.54 s (215 before gate 8, plus 12 added).
  - Vitest: **4 files, 72 tests passed**.
  - deploy-check: "no issues (1 silenced)", and the `DJANGO_DEBUG=true` run was refused.
  - pip-audit: no known vulnerabilities; `npm audit --omit=dev --audit-level=low` and `npm audit --audit-level=high` each found 0.
  - `make secrets`: "0 commits scanned, no leaks found". This is **vacuous**: the branch has no commits yet.
  - Frontend build passed.
- Outside `make check` (CI steps): `make db-check` passed 3/3 assertions; `make secrets-dist`: no leaks; `make workflow-lint`: zizmor exit 0 and policy "OK (1)".
- Flakiness: `make test-backend` was run three times in total, with 227 passed each time. The NT3-10 test took 5.00 s each time against a 6 s limit. No flaky behaviour seen.
- Not run: `make migrate` (instructed), `make setup` / `make run`, CI on GitHub (no repository), shellcheck.

### 8.5 Findings and open points
1. **SC-03 vs NT3-03 on `"False "`** (REVIEW, security-engineer or orchestrator decides; non-blocking). The implementation and `test_bool_false` follow SC-03: the value is stripped first, so it parses as false. NT3-03 says it should raise. Neither reading lets DEBUG turn on. If NT3-03 wins, the change is to the production reader plus moving `"False "` and `" True "`/`" 0 "` from the accepting tests into `test_bool_rejects_anything_else`. QA did not change either test.
2. **`make check` is not "everything CI runs"** (low). The Makefile help says it is, but `db-check`, `workflow-lint` and `secrets-dist` are CI-only, and `lint-shell` skips silently when shellcheck is missing. Proposal: either add the three targets to `check` (db-check re-runs the bootstrap on the dev DB) or reword the help text and `testing-strategy.md`.
3. **The gitleaks history scan proves nothing until the first commit** (low). Run `make secrets-staged` before the first commit, and `make secrets` after it.
4. **zizmor does not cover SC-31/SC-37 faults** (info). Explicit `persist-credentials: true` and a workspace `upload-artifact` are caught only by `scripts/ci/check-workflows.sh`. A permanent self-test for that script with a bad fixture would make NT3-30 repeatable. This is a follow-up and needs a decision on where the fixture lives.
5. **Criterion 7 "at 360 px" has weak evidence** (low). jsdom has no layout. The real check belongs to Playwright (0008).

## 9. Security review
*(security-engineer, gate 9, 2026-10-01. Mode 2: an independent review of the uncommitted working tree on `feat/0003-scaffold-and-ci`. I read every file outside `docs/` and `.claude/`, and I did not rely on the summaries in 7 or 8. **Verdict: PASS WITH RISKS.** There are no critical, high or medium findings. Six low findings follow, and the residual risks in 9.6 are the human's to accept.)*

### 9.1 Scope
I reviewed all 82 new non-ignored files outside `docs/` and `.claude/`. The security-relevant ones:
- **Config and secrets:** `backend/config/{env,validation}.py`, `config/settings/*.py`, `wsgi.py`, `manage.py`, `.env.example`, `scripts/dev/init-env.sh`, `compose.yaml`.
- **Endpoints and errors:** `config/urls.py`, `rms/core/{health,middleware,context,logging}.py`, `rms/core/api/{errors,permissions}.py`.
- **DB roles (the RLS foundation):** `scripts/db/bootstrap.sh`, `backend/conftest.py`, `config/tests/db_guards.py`, `scripts/ci/db-check.sh`.
- **CI and supply chain:** `.github/workflows/ci.yml`, `.github/dependabot.yml`, `.github/zizmor.yml`, `scripts/ci/check-workflows.sh`, `Makefile`, both lockfiles.
- **Frontend:** `frontend/src/lib/api/client.ts`, `vite.config.ts`, `config/pwa.ts`, `eslint.config.js`.

Not applicable in this change: tenant data, auth, uploads and webhooks (none exist, 5.6).

### 9.2 Controls SC-01..SC-42: implemented and tested?
| SC | Implementation (verified) | Test / check (verified) | Result |
|----|---------------------------|-------------------------|--------|
| 01 | `config/env.py:42,56,66,72,83,94,105,119`; `validation.py` messages name settings only | `test_env.py` canaries; `test_validation.py::test_messages_never_contain_values` | OK |
| 02 | `local.py:12`, `production.py:15` `require_str`; `test.py:23` env or `token_urlsafe(64)`; no literals | `test_*_requires_secret_key`, `test_no_settings_module_contains_a_literal_secret`; gitleaks clean | OK |
| 03 | `env.py:46-56`; `base.py:18` DEBUG False | `test_env.py:39-56`; ruling in 9.4 | OK |
| 04 | `env.py:109-122`; `local.py:15`, `test.py:25-30` | `test_local_refuses_real_hostname` etc. | OK |
| 05 | `validation.py:247-284`; list reader `env.py:76-84` | `test_rule_fails[7..12-*]` | OK |
| 06 | `env.py:98-106`; `production.py:32`; `operations.md:69` | `test_proxy_header_*` | OK |
| 07 | `production.py:34`; `conventions/backend.md:39`; CI `make deploy-check` | `make deploy-check` run (see F1) | OK |
| 10 | `base.py:49`; `health.py:37-47`; `statement_timeout` `bootstrap.sh:60` | `test_ready_returns_within_connect_timeout` | OK |
| 11, 14 | `urls.py` holds only the health views; DenyAll default `base.py:85` | `test_routes.py` scan + self-test; it fails closed on composed permissions | OK |
| 13 | `errors.py` has static messages; `csrf_failure` drops `reason`; handler400/403 `urls.py:17-18` | `test_errors.py` | OK |
| 15 | `base.py:31`; `conventions/backend.md:50` carry-forward | `test_csrf_*` | OK |
| 16 | `middleware.py:54-74` (independent of order) | `test_headers.py` matrix | OK |
| 18 | `middleware.py:32-51` set/reset in `finally` | `test_request_id.py` | OK |
| 19 | `logging.py:36-56` keys; `:135-157` JSON-native only; `:143-145` request becomes `{method,path}`; `:160-180` scrub; `:229,252` DB logger ≥ WARNING; `backend.md:63` | `test_logging.py` | OK |
| 20 | `logging.py:70-126` copies, depth 8, cycle guard, never raises | NT3-20 tests | OK |
| 22 | `bootstrap.sh`: `set -euo pipefail`, no `-x`, `\getenv`, logging off + terse, `format(%I)`+`\gexec`, name regex, no DO blocks | `db-check.sh` re-run (CI); implementer canary (7) | OK |
| 23 | `compose.yaml:178-179,187` | `db-check.sh:85-100` | OK |
| 24 | `db_guards.py:84-101` with `sql.Identifier`; guard queries `:104-176` | `test_db_guards.py` (11) | OK |
| 25 | `conftest.py:26-55` (`pytest.exit(returncode=3)`); `test.py:41-44` | NT3-25 tests + one-time check (7) | OK |
| 26 | `init-env.sh` (openssl, umask 077, `mv -n`, 0600, no echo, key-set and placeholder checks); CI mask step `ci.yml:42-48` | `test_init_env.py` | OK |
| 27 | `.gitignore:2-4` matches; CI clean-tree step `ci.yml:65-72` | CI only | OK |
| 28 | `compose.yaml:174-184` explicit mapping; digest pin `:173`; no `compose config` anywhere | review | OK (DB_NAME ruled in 9.4) |
| 30 | `ci.yml:11-13` push and pull_request only | zizmor + policy script | OK |
| 31 | `persist-credentials: false` ×4; `permissions: contents: read` `:15-16`; no `secrets.*` | policy script only (F2) | OK |
| 32 | SHA pins with version comments; images by digest; `pip-audit==2.10.1`; `UV_VERSION`; `.nvmrc`. **I checked all 3 SHAs with `git ls-remote` against the upstream tags: each is the tag commit** | zizmor `unpinned-uses` hash-pin + script | OK (F5, F6) |
| 33 | No `${{ }}` in any `run:` | zizmor + awk check | OK |
| 34 | `audit` job installs nothing; `--disable-pip`; `uv sync --locked`; `npm ci --ignore-scripts` | review | OK |
| 35 | `Makefile:139-145` `--strict`, both npm audits | `make audit` run | OK |
| 36 | `--redact`, `fetch-depth: 0`, `:ro`; no `.gitleaks.toml`, no inline allow comments | review; NT3-36 one-time (7) | OK (F4) |
| 37 | No artifact or env-dump steps; on failure only `docker compose logs db` | policy script only (F2, F3) | OK |
| 38 | Human; `operations.md:52-56` | — | Open (9.6) |
| 39 | No auto-merge; 4 ecosystems; 7-day cooldown | review | OK |
| 40 | `client.ts:60-69` allows only `/api/` paths after resolution, plus `redirect: "error"` | `client.test.ts` | OK |
| 41 | `vite.config.ts:186-187`; no `VITE_*` secrets | `make secrets-dist` run | OK |
| 42 | `vite.config.ts:191-194,201` | `config.test.ts` | OK |
| 29 | Carried to 0004 | — | Carried |

Every NT3 item maps to evidence as 8.2 lists it. I re-checked NT3-03, -11, -19, -24 and -30 in the code. NT3-03 is amended by the ruling in 9.4.

### 9.3 Findings
- **F1 [low] `Makefile:130-133`. The deploy-check negative accepts any failure.** The `DJANGO_DEBUG=true` run sends all its output to `/dev/null` and counts any non-zero exit as "refused". **Scenario:** a later edit breaks the command for an unrelated reason (lock drift, import error, a missing tool), or the `DJANGO_DEBUG` check is removed. The negative still reports success, so SC-07's "fails on debug" stops proving anything. The pytest subprocess case `test_production_refuses_bad_env[debug]` still covers the rule, which is why this is low. **Fix:** capture stderr and require the value-free message `DJANGO_DEBUG must be false` in it.
- **F2 [low] `scripts/ci/check-workflows.sh`. The only SC-31/SC-37 control has no permanent self-test.** zizmor does not flag an explicit `persist-credentials: true` or a workspace `upload-artifact` (QA verified this in 8.2). A regex regression in this script would switch both controls off silently. **Fix (ruling on the REVIEW item: yes, a permanent self-test is needed):** add bad fixtures under `scripts/ci/testdata/`. Never put them under `.github/workflows/`, where GitHub would run them. Use one fixture per policy rule. `make workflow-lint` must assert that the script exits 1 on each fixture and 0 on the real workflow. I prefer this done in 0003, because it is cheap. If it is deferred, record it in `docs/risks.md` and land it before the next workflow edit.
- **F3 [low] `scripts/ci/check-workflows.sh:63`. The SC-37 tripwire misses obvious env dumps:** `cat .env`, `set`, `export -p`, `declare -p` and `compgen -v`. **Scenario:** a debug step prints the env file. The `::add-mask::` step limits the damage to the values it masked (passwords, secret key), and it masks them only after it runs. **Fix:** extend the pattern. The read through `< .env` in the mask step does not conflict with a `cat`/`less`/`head`/`tail … .env` pattern. Add a fixture for each case (F2).
- **F4 [low] `Makefile:22-24`. The gitleaks container gets more than it needs.** Locally it mounts the whole repo root, which includes the gitignored env file. `secrets-dist` scans only `frontend/dist`, yet it mounts the root too. The container also has network access. The mount is digest-pinned, `:ro` and `--rm`, so this is defence in depth against a compromised image (A8). **Fix:** add `--network none` to `GITLEAKS`, and mount only `frontend/dist` for `secrets-dist`.
- **F5 [low] `Makefile:141,157`. Only the top-level tools are pinned.** `uvx pip-audit==2.10.1` and `uvx zizmor==1.30.1` pin the top-level package, but their transitive dependencies resolve fresh on every run. SC-32 asked only for the top-level pin, so its letter is met. The jobs that run these hold no secrets and a read-only token, so the impact is limited to a false "clean" audit result. **Fix (follow-up):** add `uvx --exclude-newer <date>`, or use a hashed tool requirements file that Dependabot updates.
- **F6 [low] `Makefile:157`. zizmor runs `--offline`.** This disables `impostor-commit`, `known-vulnerable-actions` and `ref-version-mismatch`. I did the impostor-commit check by hand for the current three SHAs, and all match their upstream tags (9.5). **Fix and condition:** see the ruling in 9.4.

Concurred, carried forward. These are not findings against 0003, because no tables exist yet:
- 7 follow-up 1: the app role gets DML on `django_migrations` through default privileges. A compromised app connection could then mark the 0004 RLS migration as applied. This must be revoked in 0004. data-engineer; I treat it as **required for 0004**.
- 7 follow-up 2: the `postgres` maintenance DB keeps PUBLIC `CONNECT`/`TEMP`. Low, data-engineer.
- SC-29: carried to 0004 as planned.

### 9.4 Rulings on the REVIEW items
1. **SC-03 vs NT3-03 on `"False "`. SC-03 wins, and NT3-03 is amended.** SC-03 is the control, and it says "after strip" explicitly. Stripping matches every other reader (`env.py:24-29`), so a variable means the same thing in every reader. The threat T3-03 is a falsy-looking value read as *truthy*. Stripping cannot cause that: `"False "` gives `false`, the fail-safe direction. Production also hard-codes `DEBUG=False` (`production.py:14`), and validation rule 1 rejects any `DJANGO_DEBUG` that parses as true. Listing `"False "` in NT3-03 was a drafting error in my threat model. **NT3-03 now reads:** `"no"`, `"off"`, `"yes"`, `"on"` → raise; `"False "`, `" 0 "` → false; `"true"`, `"1"` → true; unset → false. The current `test_env.py:39-56` already matches this. No code change.
2. **`SILENCED_SYSTEM_CHECKS = ["security.W021"]`: accepted.** W021 is only "HSTS preload not set". Preload is a separate human decision (6.2), and HSTS itself is enforced by rule 6. The exact-list assertion at `test_validation.py:366` stops any other ID from being silenced quietly. Condition: silencing any further check is a security REVIEW.
3. **`exc` traceback field in logs: accepted.** Logs stay server-side, and no error body carries exception text (SC-13, `test_500_is_generic`). Stdlib `formatException` includes no local variables. The SC-19c scrub covers the field (`test_logging.py:252`). Readiness logs only the class name. Residual: exception messages can hold user input or personal data; the 0005 personal-data redaction follow-up must cover `exc` too. Condition: any future crash reporter or log shipper (Phase 10) receives only the formatter's scrubbed output, never raw `exc_info`.
4. **zizmor `--offline`: accepted for CI, with a condition.** An online run would need a token in the workflow, which SC-31 deliberately avoids. Condition (`operations.md`, to add): every change to a `uses:` SHA, Dependabot PRs included, gets the impostor-commit check before merge. That is either a local `zizmor` run (online, with a read-only token) or `git ls-remote <repo> refs/tags/<tag>` matching the pinned SHA. The reviewer records it in the PR.
5. **pytest `>=9.0.3,<10`: accepted.** It is dev-only, the range excludes the flagged 8.4.2 (`pyproject.toml:14`), and `pip-audit --strict` is clean. I read the adapted log tests: they wire a real handler exactly like the console handler (`test_logging.py:45-57`). No assertion was loosened.
6. **The `db` container receiving `DB_NAME`: accepted.** It is a non-secret identifier and `bootstrap.sh:19` needs it. SC-28 aims to keep `DJANGO_SECRET_KEY` and the whole env file out of the container, and that is met (`compose.yaml:174-184`).
7. **Is the policy script the only check for SC-31/SC-37? Yes, and a permanent self-test is required.** See F2.

### 9.5 Verification (run by me, 2026-10-01, local)
- `make test-backend`: 227 passed, against the running `rms-db-1` (healthy, `127.0.0.1:5432`).
- `make deploy-check`: "no issues (1 silenced)", and the debug run was refused.
- `make workflow-lint`: zizmor 1.30.1 `--offline` reported "No findings"; `check-workflows: OK (1)`.
- `make audit`: pip-audit 2.10.1 found no known vulnerabilities; `npm audit --omit=dev --audit-level=low` and `npm audit --audit-level=high` each found 0.
- `make secrets-dist`: gitleaks v8.30.1 (digest-pinned image) found no leaks in `frontend/dist`.
- gitleaks `dir --redact` over a scratchpad copy of all 169 non-ignored files (`git ls-files --cached --others --exclude-standard`, so the env file was excluded): no leaks. A grep for private-key headers, AWS/Stripe/GitHub/Slack key prefixes, `gitleaks:allow` and literal `password|secret|token = "…"` assignments found nothing.
- `git ls-remote` against GitHub: `actions/checkout` v7.0.1, `actions/setup-node` v7.0.0 and `astral-sh/setup-uv` v10.2.0 each resolve to the pinned SHA.
- **Not run:** `make secrets` (git history). There are no commits, so the result would be vacuous; see 9.6. shellcheck is not installed locally; CI requires it. CI on GitHub: no repository exists. I did not read the env file.

### 9.6 Residual risks for the human (not accepted by security)
- **SC-38 not applied:** until the repository exists and the branch ruleset, fork-approval setting and read-only token default are set, CI is advisory. The gate-6 approval leaves this to the owner at acceptance (gate 12).
- **The history secret scan is vacuous:** run `make secrets-staged` before the first commit and `make secrets` after it. The first CI run on GitHub is the first real history scan.
- **F1-F6 (low):** fix them, or accept each in `docs/risks.md`. I recommend fixing F1-F4 in this change, because each is a few lines, and tracking F5 as a follow-up. F6 needs only the `operations.md` condition.
- R25 and R16: already accepted or recorded; unchanged.

### 9.7 Verdict
**PASS WITH RISKS.** No BLOCK condition is met:
- Both endpoints declare an explicit permission, and the default is DenyAll with a route scan.
- No tenant data exists. The app role is proven to be non-owner, NOBYPASSRLS and member of nothing.
- No secret is in code, fixtures or docs (scanned).
- No token is readable by JavaScript: there is no auth yet, and the CSRF cookie is non-HttpOnly by design per `api.md`.
- No unvalidated input reaches SQL, shell or URLs: bootstrap names are regex-checked and quoted by psql, test-DB identifiers go through `sql.Identifier`, and the client path is allow-listed.
- The L3 approval is recorded.

Every control that 5.9 named as blocking is implemented and tested: SC-22, -24, -25, -30, -31 and -36.

### 9.8 Round-trip 1 re-review
*(security-engineer, 2026-10-01. I re-read `Makefile` (`GITLEAKS_RUN`, `deploy-check`, `secrets-dist`, `workflow-lint`), `scripts/ci/check-workflows.sh`, `scripts/ci/test-check-workflows.sh`, the 26 fixtures in `scripts/ci/testdata/` and `docs/process/operations.md`. I did not rely on the backend round-trip notes in 7.)*

| Finding | Fix (verified in code) | Evidence | Status |
|---------|------------------------|----------|--------|
| F1 | `deploy-check` captures stderr to a temp file and passes only on `DJANGO_DEBUG must be false` (`config/validation.py:80`). Any other failure fails the target, and the stderr is not printed | `make deploy-check`: "no issues (1 silenced)", then "refuse DJANGO_DEBUG=true" | Closed |
| F2 | `test-check-workflows.sh` requires exit 1, the expected message and no other failure for each fixture. Fixtures live outside `.github/workflows/`, so GitHub never runs them and zizmor (scoped to `.github/workflows`) never scans them. It runs inside `make workflow-lint`, which CI's `secrets` job calls | `make workflow-lint`: zizmor no findings; `check-workflows: OK (1)`; `test-check-workflows: OK (26 fixtures rejected as expected)` | Closed |
| F3 | `dump_re` and `read_re` at `check-workflows.sh:69-71`; fixtures for env, printenv, set, export -p, declare -p, compgen -v, cat and quoted tail | Self-test above | Closed, with a known limit (below) |
| F4 | `GITLEAKS_RUN` adds `--network none`. `secrets-dist` mounts only `frontend/dist` read-only and checks first that it exists | `make secrets-dist`: no leaks | Closed |
| F5 | Not changed; follow-up 4 | — | Open (low, follow-up) |
| F6 | `operations.md:48` gives the impostor-commit check for every `uses:` SHA change, Dependabot included, with the result recorded in the PR. It matches ruling 9.4 #4 | Doc read | Closed |

**New REVIEW item: inline-trigger regex (`check-workflows.sh:16`). Confirmed.** It strictly tightens SC-30 and loosens nothing. The real workflow still passes, and `on: [push, pull_request]` passes too (no false positive). I probed it with scratch workflows (deleted afterwards):

| Form | Result |
|------|--------|
| `on: [push, workflow_dispatch]` | Caught |
| `on: [push, pull_request_target]` | Caught |
| `on: workflow_run` | Caught |
| `"on":` with block-list items | Caught |
| `pull_request` vs `pull_request_target` | Correctly distinguished by the whole-word match |

The new regex also proves on its own that the gap was real.

Gaps that remain (line-based tripwire):
- `"on": {issue_comment: {}}` (a quoted `on` key with an inline mapping);
- quoted trigger keys in block form (`"workflow_dispatch":`, `'issue_comment':`);
- a flow list that spans lines (`on: [push,` then `workflow_dispatch]` on the next line).

zizmor's `dangerous-triggers` covers `pull_request_target` and `workflow_run` in every form, so the residual gap is limited to `issue_comment`, `workflow_dispatch`, `repository_dispatch` and `pull_request_review_comment`, written in unusual YAML.

- **F7 [low] `scripts/ci/check-workflows.sh:16`. Quoted or multi-line forms of the non-zizmor triggers escape SC-30.** **Scenario:** a later edit adds `"issue_comment":` and comment-triggered runs start in the base-repo context. Impact is bounded: the workflow-level `contents: read`, no `secrets.*`, and SC-38's read-only default token. **Fix:** make the trigger names and the `on` key quote-tolerant (`["']?`), and treat every line from `on:` up to the next top-level key as trigger scope. Add three fixtures. Better still, use an allow-list: fail unless the parsed trigger set is exactly `{push, pull_request}`. Do this in 0003 if cheap; otherwise record it as a follow-up.
- **Known limit of F3 (info):** `read_re` names printing commands (`cat`, `head`, `tail`, …), but not `grep`, `sed`, `awk`, `cp`, `dd` or interpreters. A step such as `grep . <env file>` would pass. This is the expected limit of a tripwire, and the CI `::add-mask::` step covers the passwords and the secret key once it has run. No action is needed beyond noting it in the script header.

**Verification (run by me):**
- `make workflow-lint`: exit 0 (the three lines in the table above).
- `make secrets-dist`: gitleaks v8.30.1 with `--network none` and a dist-only mount, no leaks.
- `make deploy-check`: passes, with the exact refusal message.
- The trigger probes in this section.

I did not read the env file.

**Final verdict (gate 9): PASS WITH RISKS.**
- F1, F2, F3, F4 and F6 are closed.
- Open lows: F5 (follow-up 4) and F7. Each is fixed, or accepted by the human in `docs/risks.md`.
- The 9.6 residual risks are unchanged: SC-38 not applied, so CI is advisory; the history secret scan is vacuous until the first commit (`make secrets-staged` before it, `make secrets` after it).
- No BLOCK condition is met.

## 10. Code review
*(code-reviewer, gate 10, 2026-10-01; read-only, pasted by orchestrator. Re-ran: ruff + mypy (37 files clean), pytest 227 passed, frontend lint/typecheck/72 tests passed.)*

**Verdict: APPROVE.** No blocker or major findings. Every criterion traces to code and tests (QA table 8.1 spot-checked). Layering clean (`rms/core` technical only); dependencies match 6.4; no scope creep. Weak traces: criterion 7 "360 px" (jsdom, Playwright in 0008); criterion 9 (see m1).

### Minor (fix before acceptance recommended)
- **m1** `Makefile:163`, `README.md:13`, `docs/process/operations.md:27` — `make check` described as "everything CI runs", but omits `db-check`, `workflow-lint`, `secrets-dist`; shellcheck skipped locally. Fix: add `workflow-lint` and `secrets-dist` to `check`; keep `db-check` out; reword to "all checks CI runs except DB assertions (`make db-check`); shellcheck skipped if not installed".
- **m2** `docs/conventions/frontend.md:97` + section 7 — docs say "at most 2 attempts"; `shouldRetryQuery` (`frontend/src/app/providers.tsx:12-15`) allows 2 retries = 3 attempts. Fix wording (or set `MAX_QUERY_RETRIES = 1`).
- **m3** `backend/rms/core/api/errors.py:88-111` — custom DRF exception handler drops DRF's `set_rollback()`. Harmless today; once requests run in transactions (0004/0005) a handled 4xx after a partial write would commit. Fix: call `rest_framework.views.set_rollback()` + test (or document obligation for 0004).
- **m4** `Makefile:130-133` — `deploy-check` negative accepts any failure. Fix: require `DJANGO_DEBUG must be false` in stderr.
- **m5** `frontend/src/app/pages.tsx:47-57`, `router.tsx:10` — `RouteErrorPage` untested. Fix: Vitest case with a throwing child route; assert heading shown, canary text absent.
- **m6** `CHANGELOG.md` — no 0003 entry. Fix: add "Added (Change 0003)" entry (orchestrator).

### Nits
- n1 `backend/config/settings/test.py:43` — `startswith("test_")` on a constant can never fail; drop or make configurable.
- n2 `local.py:15-28` / `test.py:25-53` duplicate loopback-host + migrator alias block; acceptable at two copies.
- n3 `docs/conventions/backend.md:41` — import is `django.contrib.admindocs`, only when schemas module is imported; correct sentence.
- n4 `frontend/src/lib/api/client.ts:21` — comment says "thrown synchronously"; `apiRequest` rejects. Reword.
- n5 `docs/architecture/tenancy.md:40-53` already uses built role names; section 7 follow-up 3 can close.

### REVIEW decisions
- Section 4 items (fewest deps, job queue deferred, drf-spectacular deferred, tests as app role via MIRROR + migrator alias with `DEPENDENCIES=[]`, Postgres via compose in CI): **confirmed**.
- Frontend: TypeScript ~6.0.3 (typescript-eslint 8 peer `<6.1.0`) **confirmed**, move to 7 when supported; extra devDependencies **confirmed**; `registerType: "prompt"` **confirmed for scaffold** — 0008 must ship the update prompt before any kitchen-display rollout (never-closed devices never update); placeholder palette **confirmed as placeholder**.
- Backend: pytest 9 **confirmed**; W021 silenced (pinned by test) **confirmed**; `"False "` per SC-03 **confirmed** (security to amend NT3-03); `DB_NAME` to db service **confirmed**; initdb scram + socket trust **acceptable** (security final); `exc` field **acceptable** — note for 0005: DB error DETAIL can carry personal data into logs; shellcheck local skip **acceptable** with m1 wording; zizmor offline + policy script **acceptable** (security final); gitleaks `--verbose --redact` **acceptable**.
- QA 8.5: #1 as above; #2 = m1; #3 run `make secrets-staged` before first commit and `make secrets` after; #4 follow-up; #5 Playwright in 0008.

### Risks
`make secrets` meaningless until first commit; CI advisory until SC-38; NT3-10 has 1 s timing headroom; exception text may carry personal data into logs from 0005.

### 10.5 Round-trip 1 re-review
*(code-reviewer, 2026-10-01; pasted by orchestrator.)* **Verdict: APPROVE.** m1–m6, n1, n3, n4 resolved (verified in code). REVIEW item — m3 test via transaction-local `set_config` probe (`RollbackProbeView`, ATOMIC_REQUESTS fixture, 200 control proves the write lands): **confirmed**; follow-up for 0004: replace/add a real row-write rollback test once a tenant table exists. New nits: fixture docstring wording "the shape 0004/0005 requests take" → fixed by orchestrator (L0) to "one shape 0004/0005 may take"; `Makefile:178` `secrets-dist` relies on serial order after `build-frontend` (acceptable, documented; add order-only prerequisite if `make -j` is ever used). Re-ran: backend 231 passed, frontend 73 passed, ruff/mypy/eslint/tsc clean.

## Result
Status: DONE (gates 3, 4, 6 written; gate 5 security analysis pending)
Changed: docs/changes/0003-scaffold-and-ci.md (sections 3, 4, 5-placeholder, 6)
Intentionally not changed: ADRs, domain-model.md, tenancy.md, conventions docs (updated during implementation per criterion 12), .claude/ rules (6.9 proposal only), change-record header (risk raise is the orchestrator's call)
Facts / assumptions: no backend/, frontend/ or .github/ exists (verified). ASSUMPTION: Django applies TEST MIRROR even when the target alias is not set up (from memory of `django.test.utils.get_unique_databases_and_mirrors`, not re-verified); the guard tests catch it either way. ASSUMPTION: Node 24 is the Active LTS as of 2026-09.
Decisions: layout, rms/core — AUTO; minimal-dependency set, job queue deferral, OpenAPI deferral — REVIEW; tests as app role via migrator + MIRROR + template — REVIEW (data-engineer, security-engineer); compose-in-CI instead of a services container — REVIEW; production validation rules, security headers — REVIEW (security blocking); raise risk to L3 — orchestrator; `.claude/rules/database.md` glob addition — APPROVAL (optional)
Open questions: 1. Raise 0003 to L3 overall? (non-blocking for design, blocking for approval flow). 2. Add `scripts/db/**` to database rule globs? (non-blocking). 3. Role names and dev timeouts — data-engineer confirm (non-blocking).
Risks: MIRROR footgun, which could run tests against the dev DB (mitigated by the conftest override and the `current_database()` guard); the migrator has CREATEDB in local/CI only and must not in production (Phase 10); CI and local both hold both DB credentials (acceptable below staging; R16 check deferred).
Verification: design only; no commands run beyond reading docs and listing directories.

## 12. Acceptance — product owner, 2026-10-01
- Change 0003 accepted.
- F5 (uvx tool transitive deps unpinned) and F7 (policy script misses quoted/unusual trigger syntax) accepted as low risks R26/R27, with fixes as later Phase 2 follow-ups.
- GitHub repository: `git@github.com:SujanSapkota0923/restaurant-management-system.git` added as remote `origin` (not pushed). SC-38 settings in `docs/process/operations.md` must be applied by the owner in GitHub before any merge to `main`; until then CI is advisory (R28).
- First commit approved after `make secrets-staged`; no push.
- Carried to 0004: SC-29 (mirror flush), revoke app-role write on `django_migrations`, real row-write rollback test, PUBLIC CONNECT/TEMP on `postgres` DB (low).

