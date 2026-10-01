---
name: review-code
description: Independent RMS code review procedure — requirement traceability, design conformance, architecture boundaries, complexity, duplication, error handling, tests, docs and scope creep — with severity-ranked findings and a clear verdict. Use at the Code Review gate or when asked to review any diff.
---

# review-code

## Purpose
A second pair of eyes that catches what the implementer could not see.

## When to use
- Code Review gate; any "review this" request.

## When NOT to use
- Deep security analysis — `review-security` (run in parallel).

## Inputs
- The diff, the change record, `docs/conventions/`, relevant architecture docs.

## Procedure
1. Read the change record first so you judge against intent, not taste.
2. Read the whole diff, then the surrounding code of each changed function.
3. Check, in order:
   1. **Correctness** — does it do what the criteria say, including edge/failure cases?
   2. **Traceability** — each criterion has code and a test.
   3. **Design conformance** — matches the approved design; deviations are findings.
   4. **Boundaries** — no cross-context reach-ins, no business logic in views/components that belongs in services, no circular deps.
   5. **Data safety** — transactions around multi-step writes, no partial state on error.
   6. **Simplicity** — no speculative abstraction, dead code, or config for hypothetical needs; reuse over new helpers.
   7. **Duplication** — logic already existing elsewhere.
   8. **Errors** — handled at the right layer, user-facing messages sensible, nothing swallowed silently.
   9. **Tests** — negatives present, deterministic, test the behavior not the implementation.
   10. **Scope** — every changed line is required by the record.
   11. **Docs** — updated where behavior changed.
4. Confirm or reject each `REVIEW`-class decision listed in the record.

## Output
Findings `[blocker|major|minor|nit] path:line — problem — suggested fix`, then verdict `APPROVE` (no blocker/major) or `CHANGES REQUESTED`.

## Safety constraints
- Read-only. Findings must cite code, not guesses.

## Verification
Every finding has a location; verdict follows the rule above.
