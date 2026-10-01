# ADR-0004 — Technology stack

- **Status:** Accepted (product owner, 2026-09-30, change 0002)
- **Date:** 2026-09-30
- **Deciders:** product owner

## Context
The brief says not to choose technologies prematurely. A stack is nonetheless needed before Phase 2 can start, and the team already knows the legacy stack. This ADR is a proposal to be decided in Phase 1, together with Q19 (offline), Q21 (languages) and Q23 (PWA vs native).

## Options considered
1. **Python / Django + DRF + PostgreSQL; React + TypeScript + Vite** — team familiarity (legacy), mature auth/session/CSRF/ORM/migrations, admin tooling, strong PostgreSQL support incl. RLS via raw migrations. Cons: RLS integration is not built in (needs a small tenant-context layer); async/realtime needs Channels or SSE.
2. **Node/TypeScript (NestJS or similar) + PostgreSQL; React** — one language end to end. Cons: team retrains; more assembly for auth/session/migrations.
3. **Native mobile apps (React Native/Flutter) + API** — best device integration. Cons: store distribution, two release pipelines; likely unnecessary if a PWA meets needs (Q23).

## Decision
Option 1:
- Backend: Python 3.12+, Django 5.x LTS line, Django REST Framework, PostgreSQL 16+, a job queue (Celery + Redis, or a PostgreSQL-backed queue to avoid Redis — decide in Phase 2).
- Frontend: React + TypeScript (strict) + Vite, TanStack Query, React Router, Tailwind; installable PWA.
- Tooling: uv, ruff, mypy, pytest; npm, ESLint, Vitest, Playwright; Docker for local dev.
- No legacy dependency (django-tenants, SimpleJWT) carries over by default: tenancy is ADR-0003, sessions ADR-0006.

## Consequences
- Positive: fastest path with lowest learning cost; mature security defaults.
- Negative: two languages; realtime needs a deliberate choice in Phase 5.
- Follow-ups: stack-specific skills (Django backend, React frontend) created once accepted; fill "If ADR-0004 is accepted" sections of `docs/conventions/`.

## Revisit when
Offline-first becomes a hard requirement (Q19), or native device features are required (Q23).
