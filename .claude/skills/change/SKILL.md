---
name: change
description: Orchestrate any RMS change request (feature, bug fix, refactor, schema/permission change) through risk classification, change record, gated agent delegation, human approvals and a final engineering report. Use in the main session whenever the user asks to add, change, fix or remove RMS behavior. Not for pure questions about the codebase.
argument-hint: <change request in plain words>
---

# change — orchestrate a change through the gates

## Purpose
Turn a request like "Add partial payment support to orders" into a safe, reviewed, documented change without touching unrelated parts of the system. The main session runs this skill; it is the orchestrator.

## When to use
- Any request that changes RMS behavior, data, APIs, UI, permissions, infrastructure or docs.
- Resuming an open change record.

## When NOT to use
- Pure questions ("how does X work?") — answer directly, read-only.
- Changing the engineering system itself — use this skill, but the change is automatically `APPROVAL` (see `docs/process/risk-and-approval.md`).

## Inputs
- The request (`$ARGUMENTS`) or an existing change record path.

## Procedure

1. **Orient.** Read `docs/product/roadmap.md` (is the relevant phase open?), `docs/process/workflow.md`, `docs/process/risk-and-approval.md`. If the phase is not open, tell the user and ask whether to proceed.
2. **Classify.** Assign `L0`–`L3` using the table and escalation triggers. State the reason in one line.
3. **L0 fast path.** Make the edit, self-check, report. Stop.
4. **Open the record.** Copy `docs/changes/_template.md` to `docs/changes/NNNN-slug.md` (next free number). Fill section 1.
5. **Run gates** per `workflow.md` for the risk level. For each gate:
   - Delegate to the owning agent via the Agent tool with: the change record path, the gate name, and what output to write into which section.
   - Run independent gates in parallel (one message, several Agent calls).
   - Read the agent's `## Result`. If `NEEDS APPROVAL` or blocking open questions: ask the user (AskUserQuestion, concise options, recommended option first), record the answer in the change record, then continue.
   - If agents conflict, state both positions and the trade-off, recommend one, and decide — or ask the human if the conflict is `APPROVAL`-class.
6. **Approval stops.** L3: stop after gate 6 for design approval. Any `APPROVAL` decision: stop where found.
7. **Implementation.** Delegate to `backend-engineer` / `frontend-engineer` (parallel when the API contract is fixed). Never implement L2+ work in the main session.
8. **Verify.** Gates 8–10: `qa-engineer`, then `security-engineer` (review mode) and `code-reviewer` in parallel. Findings go back to implementers. Two round-trips on the same finding → ask the human.
9. **Document.** `tech-writer` updates docs and changelog.
10. **Accept.** Check the definition of done in `workflow.md`. L3 needs explicit human acceptance. Set record status `Done`.
11. **Reflect.** If the change exposed a recurring problem (same finding twice, missing rule, unclear ownership), append a proposal to `docs/process/improvement-log.md`. Do not edit `.claude/` directly.

## Safety constraints
- Never skip a gate the risk level requires because the change "looks simple". Lower the level only with a written reason.
- Never proceed past a `BLOCK` without human risk acceptance recorded in the record and `docs/risks.md`.
- Do not batch unrelated requests into one change record.

## Expected output (final report to the user)
```
Change NNNN — <title>   Risk: Lx   Status: Done | Blocked | Awaiting approval
Changed: <files/areas>
Intentionally not changed: <items>
Tests: <commands and results>
Security review: <verdict + open findings>
Code review: <verdict>
Docs updated: <list>
Approvals obtained: <what, when>
Unresolved risks / follow-ups: <list>
```

## Verification
- Every required gate section in the change record is filled.
- Test commands were actually run and results quoted.
- The report lists nothing that was not actually done.

## Example
"Add partial payment support to orders" → contains payment state and money → `L3`. Requirements analyst surfaces questions (split by item or by amount? can a partially paid order be cancelled? refunds?). Orchestrator asks the human. Architect finds impact on Orders, Billing, Reports, Audit. Data engineer designs payment-allocation table + additive migration. Security engineer threat-models amount tampering, replay, race on final payment. Human approves design. Implementation, tests (including two concurrent payments exceeding the balance), reviews, docs. Human accepts.
