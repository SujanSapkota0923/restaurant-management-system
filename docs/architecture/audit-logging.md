# Audit Logging

**Status:** Proposed. Owner: `architect` + `security-engineer`. Procedure: `audit-logging` skill.

## Purpose
Answer for every business-critical action: who, what changed, when, which restaurant, which resource, previous state, new state, outcome.

Audit is **not** application logging. Logs are for operators and may be sampled or rotated; audit events are business records, complete and retained per Q20.

## What is audited (v0 list)
- Access: staff account created (C6.11); owner invitation created/accepted/revoked (C6.6); membership suspended/reactivated/removed; role created/changed/deleted; permission granted/revoked; staff password reset by a manager (C6.15); device paired/revoked (C6.14).
- Identity/security events: login success/failure, logout, password change/reset, email verified, MFA changes, permission-denied on sensitive actions.
- Restaurant settings changed.
- Menu: item/category created, price changed, availability changed, deactivated.
- Tables: created, changed, deactivated.
- Orders: cancelled, discounted, line voided after sending to kitchen, reopened.
- Billing: payment recorded, refund, bill closed/reopened.
- Inventory: adjustment, count, write-off.
- Reservations: cancelled / no-show marked (pending Q17).
- Platform operator access to tenant data (break-glass).

Routine high-volume events (adding a line to an open order) are captured by the owning context's own history, not the audit log, unless requirements say otherwise.

## Event shape (proposed)
`id`, `tenant_id`, `occurred_at`, `actor_user_id`, `actor_membership_id`, `actor_type` (user / device / system / platform), `action` (`<resource>.<past_tense_verb>`), `resource_type`, `resource_id`, `before` (changed business fields only), `after`, `reason` (optional), `outcome` (success / denied / failed), `request_id`, `ip` (hashed or truncated per privacy decision).

Staff personal data in `before`/`after` (C6.22): name and contact changes are recorded as "changed" without values; role, permission, status and device-profile changes record full old and new values; login identifier changes record a keyed hash of old and new.

## Rules
- One audit API; no ad-hoc inserts or log lines as audit.
- Success events are written in the **same transaction** as the change.
- Denied/failed events are written outside the rolled-back transaction.
- Append-only for the application role (no UPDATE/DELETE grants); tenant-scoped with RLS.
- Redaction: never secrets, tokens, passwords, payment instrument data.
- Readable in-app only with `audit.view`.

Legacy note: `../rms` audited through generic model signals capturing all field diffs; RMS uses explicit business events instead (`docs/legacy/reference-assessment.md`).
