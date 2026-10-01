---
name: domain-modeling
description: Model RMS business concepts as bounded contexts, aggregates, entities, value objects, invariants, state machines and domain events, and keep the ubiquitous language in docs/architecture/domain-model.md accurate. Use when a change introduces or reshapes a business concept or its lifecycle.
---

# domain-modeling

## Purpose
Give each business concept one clear owner, one name, and explicit rules.

## When to use
- New concept (e.g. "payment allocation", "course", "station").
- Changing a lifecycle (order states, reservation states).
- Two modules disagree about who owns data.

## When NOT to use
- Table/column-level design — use `database-design` after this.
- UI-only changes.

## Inputs
- Confirmed requirements; `docs/architecture/domain-model.md`; ADRs.

## Procedure
1. Use the existing vocabulary. A new term needs a definition and must not collide with an existing one.
2. Assign the concept to a bounded context. If none fits, propose a new one (`APPROVAL`).
3. Identify the aggregate root and its consistency boundary: what must be consistent in one transaction vs eventually.
4. Write invariants as plain sentences ("An order's paid amount never exceeds its total").
5. For lifecycles, write the state machine: states, allowed transitions, who (permission) may trigger each, side effects, which are terminal/reversible.
6. Define domain events emitted on meaningful transitions (for audit, kitchen display, reports).
7. Identify cross-context interactions and their direction (who calls/listens to whom). No cycles.
8. Note history requirements: which values must be snapshotted (price at time of order, tax rate at time of payment).

## Safety constraints
- Every tenant-owned concept belongs to exactly one tenant. Anything cross-tenant is platform-level and `APPROVAL`.
- Do not model features the requirements do not confirm.

## Expected output
Updates to `domain-model.md` (marked `Proposed` until accepted) and the architecture section of the change record.

## Verification
Each invariant maps to an enforcement point (DB constraint, service check, or both) that `data-engineer`/`backend-engineer` can implement and `qa-engineer` can test.
