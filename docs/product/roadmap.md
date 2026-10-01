# Roadmap

Each phase has an exit gate. A phase is **Open** only when the previous phase's exit criteria are met and the human says so. The `change` skill checks this before starting work.

| Phase | Name | Status |
|-------|------|--------|
| 0 | Engineering system bootstrap | **Done** (2026-09-30) |
| 1 | Decisions and discovery | **Done** (2026-09-30, change 0002) |
| 2 | Foundation (walking skeleton) | **Open** (2026-09-30) |
| 3 | Restaurant setup: tenant onboarding, settings, staff, roles | Not open |
| 4 | Menu and tables | Not open |
| 5 | Orders and kitchen | Not open |
| 6 | Billing and payments | Not open |
| 7 | Dashboard, history, reports | Not open |
| 8 | Inventory | Not open |
| 9 | Reservations | Not open |
| 10 | Production readiness and launch | Not open |

Order after Phase 3 is a proposal; the human may reorder 4–9.

## Phase 1 — Decisions and discovery
No production code.
- Answer blocking open questions in `requirements.md` (at least Q1, Q4–Q8, Q19–Q21, Q23).
- Accept or revise ADRs 0003 (tenancy), 0004 (stack), 0005 (identity/membership/authorization), 0006 (sessions).
- `requirements-analyst`: per-area requirement briefs for Phase 3–5 areas.
- `architect`: bounded contexts in `domain-model.md` moved from `Proposed` to `Accepted`.
- `ux-designer`: navigation model and core flows (login, switch restaurant, take order, kitchen ticket).
- `security-engineer`: platform-level threat model in `security.md`.

**Exit:** blocking questions answered; ADR-0003..0006 accepted; domain model accepted; permission catalog v1 drafted.

## Phase 2 — Foundation (walking skeleton)
Critical risk (`L3`) throughout.
- Repository scaffold per ADR-0004; lint, type-check, test runners; CI pipeline with tests, dependency audit and secret scan.
- Tenancy per ADR-0003: tenant model, tenant resolution, tenant-scoped data access, RLS, isolation test harness (two-tenant fixtures).
- Identity, membership, sessions (ADR-0005/0006): owner invitation (C6.6), manager-created staff accounts with temporary passwords (C6.11, C6.15), owner email verification, login/logout, owner password reset, manager-led staff reset (C6.16), device pairing (C6.14), rate limits, CSRF.
- Authorization core: permission catalog, roles, single enforcement helper, test matrix helpers.
- Audit core: audit API, append-only store, security events.
- Observability basics: structured logs with request/tenant IDs, error tracking, health endpoint.
- Frontend shell: mobile app shell, auth screens, restaurant switcher, permission-aware navigation, error envelope handling.

**Exit:** a user can sign up/accept invite, verify email, log in, switch restaurant, and see a permission-filtered empty dashboard; cross-tenant and authz test suites green in CI; security review `PASS`.

## Phases 3–9 — Feature phases
Each area runs as one or more change records through the full gates. Exit for each: acceptance criteria met, isolation/authz/audit tests green, security and code review passed, docs updated.

## Phase 10 — Production readiness
Deployment per `docs/process/operations.md`, backups and restore drill, monitoring and alerting, load test of peak service scenarios, full security review and dependency audit, runbooks.

**Exit:** human go-live approval.
