---
name: requirements-analysis
description: Turn an RMS request into goals, testable acceptance criteria, edge and failure cases, operational context and open questions, without inventing business rules. Use at the Requirements gate or whenever a request is ambiguous.
---

# requirements-analysis

## Purpose
Make behavior explicit before anyone designs or codes it.

## When to use
- Requirements gate of any L1+ change.
- A request contains words like "support", "handle", "allow", "improve" without specifics.

## When NOT to use
- L0 changes. Pure technical refactors with no behavior change (write a one-line "no behavior change" requirement instead).

## Inputs
- The request; `docs/product/requirements.md`; `docs/product/ux-principles.md`; domain vocabulary.

## Procedure
1. **Goal.** One sentence: who wants what outcome, and why.
2. **Actors and context.** Which role(s); device (phone/tablet/kitchen display); frequency; time pressure; network conditions.
3. **Happy path.** Numbered steps in business terms.
4. **Acceptance criteria.** Numbered, each observable and testable ("Given/When/Then" or equivalent). Include permission and audit criteria.
5. **Edge cases.** Walk this checklist, keep only relevant items:
   - Zero, one, many; maximums; decimals and rounding for money/quantity
   - Concurrent actors on the same record; double tap / retry
   - State at the wrong time (cancelled order, closed table, inactive item, deactivated staff)
   - Partial failure mid-operation; network loss; device switch
   - Timezones, day boundaries, shift boundaries, restaurant closed hours
   - Deleted/renamed referenced data (menu item removed after ordering)
   - Undo / correction / reversal; who may do it
   - Different restaurant setups (counter service vs table service, single vs multi-location if in scope)
6. **Failure cases.** What the user sees and what data state results for each.
7. **Scope.** Must-have vs optional vs out of scope.
8. **Open questions.** Each: question, why it matters, suggested default, `blocking`/`non-blocking`.

## Safety constraints
- A suggested default is not a rule. Only human-confirmed rules enter `docs/product/requirements.md`.
- Never resolve money, tax, permission or data-retention questions by assumption.

## Expected output
The filled "Requirements" section of the change record.

## Verification
- Every criterion is testable by a QA engineer without asking you.
- No rule appears that is not in the request, the requirements doc, or marked as an open question.

## Example
"Kitchen should see new orders faster" → criteria: new order visible on kitchen screen within N seconds (N = open question, suggested 3s); audible cue configurable; works on flaky Wi-Fi (reconnect + catch-up with no missed or duplicated tickets).
