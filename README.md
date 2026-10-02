# RMS — Restaurant Management System

Multi-tenant, mobile-first B2B restaurant management platform.

**Status:** Phase 2 (foundations). The backend and frontend scaffold, local development environment and CI exist (change 0003), plus the tenancy foundation: tenant registry, tenant context, RLS and the isolation harness (change 0004); there are no domain features yet. See `docs/product/roadmap.md`.

## Setup
Prerequisites: Docker with Compose v2, [uv](https://docs.astral.sh/uv/), Node 24 or newer, openssl, GNU make, bash.

```sh
make setup   # env file with random secrets, dependencies, PostgreSQL, migrations
make run     # backend on http://127.0.0.1:8000, frontend dev server (Vite)
make check   # all checks CI runs except the DB assertions: lint, typecheck, migrations (incl. round trip), tests, deploy check, audit, secrets, build, bundle scan, workflow lint
```

`make check` leaves out the DB assertions (run `make db-check`) and the dev-DB catalog check (`make catalog-check`, after `make migrate`), and skips shellcheck if it is not installed (CI requires it). It does run the migration round trip, on a throwaway database.

- `make setup` creates the gitignored env file at the repo root from `.env.example`, replacing each placeholder secret with a random value. It never prints the values and never overwrites an existing file. Do not commit, print or share it.
- PostgreSQL 16 runs in Docker on `127.0.0.1:5432` only. Tests connect as the non-privileged app role to a separate `test_rms` database. `make up` / `make down` start and stop it (`down` keeps the data).
- `make help` lists every target. CI calls the per-side targets (`*-backend`, `*-frontend`).
- Run `make secrets-staged` before committing.

Details: `docs/process/operations.md` (local dev, CI, required GitHub settings), `docs/conventions/backend.md`, `docs/conventions/frontend.md`, `docs/process/testing-strategy.md`.

## Working on RMS with Claude Code
- Read `CLAUDE.md` (operating guide) and `docs/README.md` (doc map).
- Request any change with `/change <what you want>`. The main session classifies risk, opens a change record in `docs/changes/`, runs the gates with specialist agents (`.claude/agents/`), and stops for your approval where `docs/process/risk-and-approval.md` requires it.
- After a significant change or phase, run `/retro` to review the engineering system itself.

## Layout
```
CLAUDE.md                 operating guide for Claude Code (orchestrator role)
.claude/agents/           10 specialist subagents
.claude/skills/           reusable skills (workflow + knowledge)
.claude/rules/            hard project rules (always-on and path-scoped)
.claude/settings.json     tool permission guardrails
docs/                     product, architecture, conventions, process, ADRs, change records
backend/                  Django + DRF project (config/, rms/<context>/), uv-managed
frontend/                 React + TypeScript + Vite PWA, npm-managed
scripts/                  dev (env file), db (role bootstrap) and CI helper scripts
compose.yaml              local/CI PostgreSQL
Makefile                  setup, run and check entry points
.github/                  CI workflow, Dependabot, zizmor config
```

The previous prototype in `../rms` is a reference only (ADR-0002).
