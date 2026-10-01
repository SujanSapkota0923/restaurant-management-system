---
name: debugging
description: Evidence-driven diagnosis of RMS defects and production incidents — reproduce, bound, hypothesize, test, find root cause, fix at the right layer with a regression test, and write an incident note when users were affected. Use for bugs, failures, flaky tests, performance regressions and incidents.
---

# debugging

## Purpose
Fix the cause, not the symptom, and make sure it cannot silently return.

## When to use
- Any bug report, failing/flaky test, error spike, or incident.

## When NOT to use
- New features — use `change`.

## Procedure
1. **Capture facts.** Exact error text, request ID, tenant (ID only), time, environment, steps, expected vs actual. Separate reports from verified facts.
2. **Reproduce** locally or in a test. If you cannot, say so and gather more evidence rather than guessing.
3. **Bound.** When did it start (commit, deploy, data change)? Which tenants/roles/devices? Is data affected?
4. **Hypotheses.** List candidates ranked by evidence; test the cheapest discriminating one first. Record each result.
5. **Root cause.** State it with evidence (`path:line`, log line, query). Ask "why" until you reach something fixable at the right layer.
6. **Data impact.** If records are wrong, quantify and plan correction as a separate, approved change (data rewrites are `APPROVAL`).
7. **Fix** through `change` (risk-classified). Regression test first.
8. **Incident note** (if users were affected): timeline, impact, root cause, fix, prevention, in `docs/incidents/YYYY-MM-DD-slug.md`.

## Safety constraints
- Do not "fix" by loosening validation, permissions or tenant checks.
- Do not add debug logging that prints secrets or personal data; remove temporary logging before completion.
- Never test hypotheses against production data or infrastructure.

## Expected output
Root cause with evidence, fix via change record, regression test, optional incident note.

## Verification
Regression test fails before the fix and passes after; full affected suite green.
