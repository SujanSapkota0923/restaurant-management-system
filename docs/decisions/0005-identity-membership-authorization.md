# ADR-0005 — Identity, membership and permission-based authorization

- **Status:** Accepted (product owner, 2026-09-30, change 0002)
- **Date:** 2026-09-30
- **Deciders:** product owner
- **Change record:** docs/changes/0002-phase-1-discovery.md

## Context
The brief requires identity, membership and authorization to be distinct, supports custom roles and granular permissions, and warns against assuming one restaurant per user. The legacy system stored `restaurant` and `role` on the user and checked `role == "admin"` plus a JSON list of inventory permissions (`../rms/backend/apps/user/models.py`, `permissions.py`).

## Options considered
1. **Role enum on membership** — simple, but no custom roles, and checks drift to role names.
2. **RBAC: membership → roles → permission codes, plus sparse direct grants** — custom and predefined roles, granular, auditable, familiar.
3. **Attribute/policy engine (ABAC, external policy service)** — powerful; unnecessary complexity for v1.

## Decision
Option 2, as specified in `docs/architecture/authorization.md`: global permission catalog, restaurant-scoped roles (system templates copied per restaurant, protected Owner role), optional direct grants, allow-only (no deny rules), permission-code checks through one helper, default deny, escalation guards, per-request evaluation, all changes audited. Object-level rules are expressed in services where requirements demand them.

## Consequences
- Positive: meets all brief requirements; easy to test with a standard matrix.
- Negative: permission catalog becomes a governed artifact — every new code is an `APPROVAL` decision.
- Follow-ups: finalise catalog v1 and default role mapping in Phase 1 (Q9).

## Revisit when
Rules need conditions beyond membership + object ownership (e.g. time-of-shift restrictions, Q18).
