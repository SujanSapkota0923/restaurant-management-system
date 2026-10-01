---
name: impact-analysis
description: Map everything an RMS change could affect — modules, data, APIs, permissions, tenant boundary, UI, jobs, reports, docs — and confirm or raise its risk level before design. Use at the Impact Analysis gate or before any non-trivial refactor.
---

# impact-analysis

## Purpose
Prevent blind changes and surprise breakage in unrelated areas.

## When to use
- Impact gate for L2+; before renaming/moving shared code; before changing a shared model or API.

## When NOT to use
- L0/L1 changes confined to one component with no shared consumers.

## Inputs
- Change record with requirements; the codebase; `docs/architecture/`.

## Procedure
1. List the concepts the change touches; map each to its owning bounded context (`domain-model.md`).
2. Find every usage: grep models, services, endpoints, serializers/schemas, frontend API clients, tests, background jobs, reports, fixtures. Record `path:line`.
3. For each affected area, state: read-only dependency or behavior change?
4. Check the cross-cutting concerns explicitly:
   - Data: tables/columns changed, migration needed, backfill needed, historical data meaning changes?
   - API: contract change? breaking for existing clients?
   - Permissions: new action needs a permission? existing role defaults affected?
   - Tenant boundary: any new query, cache key, file path, event channel, or job that must carry tenant context?
   - Audit: new auditable action?
   - Reports/history: do past numbers change meaning?
   - UI: which screens/workflows change?
   - Docs: which pages become stale?
5. Apply the escalation triggers in `docs/process/risk-and-approval.md`; confirm or raise the level.
6. List things that look related but must **not** change.

## Safety constraints
- Read-only analysis. No code edits.
- If you cannot find all usages (dynamic access, string references), say so explicitly — do not claim completeness.

## Expected output
The "Impact analysis" section: table of area → effect → evidence, risk level with reason, and a "must not change" list.

## Verification
Every listed area has evidence (`path:line` or doc reference). Unknowns are labelled.
