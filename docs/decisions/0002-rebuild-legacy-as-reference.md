# ADR-0002 — Rebuild; treat `../rms` as reference only

- **Status:** Accepted (directed by the bootstrap brief: "rebuilding … from the beginning")
- **Date:** 2026-09-30
- **Deciders:** product owner (brief)

## Context
`../rms` is a working prototype (Django + django-tenants + React). Assessment (`docs/legacy/reference-assessment.md`) found good patterns (transactional services, idempotency, outbox, cookie auth) and structural problems (identity fused with tenancy, role-name checks, committed secrets, cascades that can delete history, unverified recent changes).

## Options considered
1. **Refactor in place** — keeps working features, but the identity/tenancy/authz foundations are the parts that need replacing, and every feature depends on them.
2. **Rebuild with the legacy as a reference** — foundations done right first; legacy mined for requirements, edge cases and proven patterns.

## Decision
Rebuild in `Rms/`. No code is copied from `../rms` without a change record justifying that specific piece. Data migration from any legacy deployment is out of scope unless the product owner says a legacy deployment has real data to keep (open question in the Phase 1 list).

## Consequences
- Longer time to first feature; far lower risk in tenancy and authorization.
- Legacy tests and screens are a requirements source for Phase 1.

## Revisit when
A legacy deployment with production data must be migrated.
