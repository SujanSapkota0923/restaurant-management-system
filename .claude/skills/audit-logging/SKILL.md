---
name: audit-logging
description: Decide what RMS actions are auditable and record them correctly — actor, membership, tenant, resource, action, before/after state, outcome, request ID — transactionally and without leaking secrets. Use when implementing or reviewing any business-critical state change, permission change, or security event.
---

# audit-logging

## Purpose
Answer "who did what, to which record, in which restaurant, when, from what to what, and did it succeed?" for every business-critical action.

## When to use
- Implementing changes to money, orders, menu prices/availability, inventory quantities, staff/memberships/roles/permissions, restaurant settings, table configuration; security events (login, failed login, password change, permission denied on sensitive actions).

## When NOT to use
- Debug/operational logging — that is observability, not audit. Do not mix the two.

## Inputs
- `docs/architecture/audit-logging.md` (event schema and the single audit API); the change's domain events.

## Procedure
1. Decide if the action is auditable using the list in `audit-logging.md`. If unsure, it is a `REVIEW` question.
2. Name the action `<resource>.<verb>` (e.g. `menu_item.price_changed`, `order.cancelled`) — stable, past tense, business meaning.
3. Record through the single audit API only — never ad-hoc log lines or direct inserts.
4. Write the audit record **in the same transaction** as the change, so neither exists without the other.
5. Capture: actor user, membership, tenant, resource type + ID, action, before/after of changed business fields only, reason (if the workflow asks for one), request ID, outcome.
6. Failed/denied attempts on sensitive actions are audited as outcome `denied`/`failed` (outside the rolled-back transaction).
7. Redact: never include passwords, tokens, secrets, full payment instrument data; minimize personal data.
8. Audit records are append-only for application code: no update/delete paths.

## Safety constraints
- Never disable or skip audit to improve performance without `APPROVAL`.

## Verification
Tests assert the audit record exists with correct actor/tenant/before/after for success, and does not exist when the transaction rolls back; denied attempts produce a denied record.
