---
name: documentation
description: Keep RMS docs true to the code — update architecture/domain/API/permission/data/workflow/setup docs, write and update ADRs, and maintain the changelog. Use at the Documentation gate, when recording an architecture decision, or when auditing docs for drift.
---

# documentation

## Purpose
A future Claude session or new developer can understand the real system from `docs/`.

## When to use
- Documentation gate; any lasting decision (ADR); doc drift audits.

## When NOT to use
- Code comments — follow the code's conventions instead.

## Inputs
- The final diff, the change record, `docs/README.md` (doc map).

## Procedure
1. From the diff, list facts that changed: concepts, states, endpoints, permissions, tables, config, commands.
2. For each, find the doc page that owns it (doc map). Update it; cite `path:line` where helpful.
3. **ADRs.** For a lasting decision (technology, boundary, cross-cutting pattern), copy `docs/decisions/0000-template.md` to the next number. Status `Proposed` until the human accepts. Never edit the decision of an `Accepted` ADR — supersede it with a new one.
4. **Changelog.** Add an entry under `## Unreleased` in `CHANGELOG.md`: Added / Changed / Fixed / Security / Removed, user-facing wording, change record number.
5. Mark anything not yet built as `Planned` with a roadmap reference.
6. Remove statements the change made false. List other drift you noticed as follow-ups.

## Safety constraints
- Never document behavior you did not verify in code.
- No secrets, real personal data, or credentials in docs.

## Expected output
Doc updates, ADR (if any), changelog entry, list of follow-ups.

## Verification
Grep the docs for old names/paths removed by the change — none remain.
