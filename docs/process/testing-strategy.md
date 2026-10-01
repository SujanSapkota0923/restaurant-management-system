# Testing Strategy

**Status:** Proposed. Tools fixed with ADR-0004; scaffold and CI built in change 0003. Procedure: `testing` skill.

## Levels
| Level | Proves | Runs against | Volume |
|-------|--------|--------------|--------|
| Unit | Pure domain logic: calculations, state machines, validators | No DB | Many |
| Integration | Services with DB: transactions, constraints, RLS, tenant scoping, authz, audit | Real PostgreSQL | Many |
| API | Contract: status codes, envelope, permissions, pagination | App + DB | Per endpoint |
| Component | UI states and interactions | jsdom | Per component with behavior |
| End-to-end | Critical journeys on a mobile viewport | Full stack | Few (login, take order, kitchen ready, take payment) |

## Tools (as built in change 0003)
| Side | Tool | Notes |
|------|------|-------|
| Backend | pytest 9 + pytest-django 4 | Against PostgreSQL 16 from `compose.yaml`, **connected as the app role** (`rms_app`) to `test_rms`. A session guard aborts the run if the connection is not the app role on the test DB, or if the role has any extra privilege (`backend/config/tests/db_guards.py`). Details: `docs/conventions/backend.md` "Tests" |
| Backend | Django test client, `RequestFactory` | API tests run with `DEBUG=False`. Test-only views live under `tests/` and are mounted with `@pytest.mark.urls` |
| Frontend | Vitest + jsdom + Testing Library | `docs/conventions/frontend.md` |
| End-to-end | Playwright | **Planned** (0008) |
| Factories | factory_boy | **Planned** (0004) |

Run with `make test` (or `make test-backend`, with `PYTEST_ARGS=...`, and `make test-frontend`). PostgreSQL must be up (`make up`).

## Always-on suites (from Phase 2)
- **Tenant isolation suite**: every tenant-scoped endpoint is exercised from tenant A against tenant B's IDs, and RLS without context returns nothing. **Planned** (0004).
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
| `backend` | `uv sync --locked`; per-run env file; PostgreSQL via compose; DB assertions (loopback port, password auth, bootstrap re-run); ruff lint + format check; shellcheck; mypy; `makemigrations --check`; pytest as the app role; `check --deploy` on production settings, which must also fail with `DJANGO_DEBUG=true`; clean working tree |
| `frontend` | `npm ci --ignore-scripts`; lint (ESLint + Prettier); type-check; Vitest; build; gitleaks over `frontend/dist` |
| `audit` | `pip-audit --strict` on the exported lockfile (dev groups included); `npm audit --omit=dev --audit-level=low` and a full-tree `npm audit --audit-level=high`, both blocking |
| `secrets` | gitleaks over the full history (redacted); workflow lint (zizmor + `scripts/ci/check-workflows.sh` + its fixture self-test `scripts/ci/test-check-workflows.sh`) |

**Planned:** migration backward check and RLS catalog check (0004); runtime-env check that migrator credentials are absent (R16, 0004/Phase 10); Playwright (0008). Main branch protection (all four jobs required, plus review) is a GitHub setting (`operations.md`). Until it is applied, CI is advisory.

## Test data
Factories with fake data, two tenants by default, frozen time. No production data in any environment below production.
