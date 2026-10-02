# Testing Strategy

**Status:** Proposed. Tools fixed with ADR-0004; scaffold and CI built in change 0003; tenant isolation harness, catalog check and migration round trip built in change 0004. Procedure: `testing` skill.

## Levels
| Level | Proves | Runs against | Volume |
|-------|--------|--------------|--------|
| Unit | Pure domain logic: calculations, state machines, validators | No DB | Many |
| Integration | Services with DB: transactions, constraints, RLS, tenant scoping, authz, audit | Real PostgreSQL | Many |
| API | Contract: status codes, envelope, permissions, pagination | App + DB | Per endpoint |
| Component | UI states and interactions | jsdom | Per component with behavior |
| End-to-end | Critical journeys on a mobile viewport | Full stack | Few (login, take order, kitchen ready, take payment) |

## Tools (as built in changes 0003 and 0004)
| Side | Tool | Notes |
|------|------|-------|
| Backend | pytest 9 + pytest-django 4 | Against PostgreSQL 16 from `compose.yaml`, **connected as the app role** (`rms_app`) to `test_rms`. A session guard aborts the run if the connection is not the app role on the test DB, or if the role has any extra privilege (`backend/config/tests/db_guards.py`). Details: `docs/conventions/backend.md` "Tests" |
| Backend | Django test client, `RequestFactory` | API tests run with `DEBUG=False`. Test-only views live under `tests/` and are mounted with `@pytest.mark.urls` |
| Frontend | Vitest + jsdom + Testing Library | `docs/conventions/frontend.md` |
| End-to-end | Playwright | **Planned** (0008) |
| Factories | factory_boy 3.3.3 | **Built** (0004). Per context in `tests/factories.py`, deterministic sequences, typed `make_*` wrappers. `docs/conventions/backend.md` "Tests" |

Run with `make test` (or `make test-backend`, with `PYTEST_ARGS=...`, and `make test-frontend`). PostgreSQL must be up (`make up`).

## Always-on suites (from Phase 2)
- **Tenant isolation suite**: every tenant-scoped endpoint is exercised from tenant A against tenant B's IDs, and RLS without context returns nothing. **Built** (0004) as the harness and its proofs in `backend/rms/tenancy/tests/`:
  - harness: `ISOLATION_DB` (transactional tests on both aliases), `two_tenants` (asserts an empty registry first, SC-29), `rows_visible_to` (non-vacuous counts, always with a positive control), and a guard that fails a transactional test without the `migrator` alias;
  - proofs on two test-only probe tables: RLS without context (0 rows, writes rejected), A against B (read, update, delete, insert, composite FK insert and update), context leaks (reused connection, `on_commit`, threads, savepoints), the tenant manager outside context, tenant-key immutability, per-tenant uniqueness, the registry column grants, and the uniform tenant-resolution 404 plus the error-response rollback matrix on test views.

  Each new tenant endpoint and table adds its own cross-tenant tests with this harness.
- **Catalog check** (C3-5): RLS, policies, grants, roles, views, definer functions, foreign keys and uniqueness on the migrated DB, with a negative test per rule. **Built** (0004), in `make test-backend`, `make catalog-check` and `make migrations-roundtrip`.
- **Source scans** (0004): `app.*` settings written only by the entry point; no raw SQL outside the data layer; the migrator alias and factories only in tests; no override of `TenantAPIView`'s closed methods. **Built**, each with a self-test.
- **Authorization matrix**: every protected route gets 401 / 403 / cross-tenant 404 / deactivated membership / success. **Planned** (0006).
- **Route inventory test**: fails if any route is neither on the public allow-list nor declares a non-`AllowAny` permission. **Built** (`backend/config/tests/test_routes.py`), including a self-test against a URLconf with unlisted routes.
- **Test-DB guard**: the run aborts unless it connects as the non-privileged app role to the test DB. **Built** (0003).
- **Audit assertions**: each auditable action writes one correct event, and none on rollback. **Planned** (0007).

## Required per change
- Acceptance criteria traced to tests.
- Negative cases for every touched permission and tenant boundary.
- Regression test for each bug.
- Concurrency test for each named race.

## CI (as built in change 0003)
`.github/workflows/ci.yml` runs on `push` and `pull_request` with four jobs:

| Job | Checks |
|-----|--------|
| `backend` | `uv sync --locked`; per-run env file; PostgreSQL via compose; DB assertions (loopback port, password auth, bootstrap re-run, no PUBLIC or app-role access to `postgres`/`template1`); ruff lint + format check; shellcheck; mypy; `makemigrations --check` on local and test settings; `make migrate` then the read-only catalog check on the dev DB; the migration round trip on a throwaway DB; pytest as the app role (includes the catalog check); `check --deploy` on production settings, which must also fail with `DJANGO_DEBUG=true`; clean working tree |
| `frontend` | `npm ci --ignore-scripts`; lint (ESLint + Prettier); type-check; Vitest; build; gitleaks over `frontend/dist` |
| `audit` | `pip-audit --strict` on the exported lockfile (dev groups included); `npm audit --omit=dev --audit-level=low` and a full-tree `npm audit --audit-level=high`, both blocking |
| `secrets` | gitleaks over the full history (redacted); workflow lint (zizmor + `scripts/ci/check-workflows.sh` + its fixture self-test `scripts/ci/test-check-workflows.sh`) |

**Planned:** runtime-env check that migrator credentials are absent (R16, Phase 10); the catalog check against deployed databases (Phase 10, R1); Playwright (0008). Main branch protection (all four jobs required, plus review) is a GitHub setting (`operations.md`). Until it is applied, CI is advisory.

## Test data
Factories with fake data, two tenants by default (`two_tenants`), frozen time. No production data in any environment below production.
