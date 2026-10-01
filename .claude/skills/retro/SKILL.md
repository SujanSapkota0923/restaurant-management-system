---
name: retro
description: Run a retrospective on recent RMS work to find repeated reasoning, repeated mistakes, recurring security or testing gaps, unclear agent ownership, missing skills/rules and doc drift, then propose (not apply) improvements to the engineering system. Use after a significant change, a phase milestone, or when the user asks to improve the agent system.
argument-hint: [change record numbers or "since <date>"]
disable-model-invocation: true
---

# retro — improve the engineering system

## Purpose
Keep the agent/skill system useful as RMS grows, without it silently drifting.

## When to use
- After an L3 change, at each roadmap phase exit, or on request.

## When NOT to use
- Mid-change. Finish or pause the change first.

## Inputs
- Change records in `docs/changes/` (all since last retro, or those named).
- `docs/process/improvement-log.md`.

## Procedure
1. Read the selected change records, especially review findings (gates 8–10) and questions raised.
2. Look for patterns:
   - Same review finding in 2+ changes → missing rule or skill guidance.
   - Same question asked in 2+ changes → missing requirement or doc.
   - Gates that added no value at a risk level → risk table may be too strict.
   - Defects found late that an earlier gate should have caught → gate or skill gap.
   - Agents overlapping or both skipping a duty → unclear ownership.
   - Docs contradicted by code → drift.
3. For each pattern write a proposal: evidence (change numbers), proposed edit (file + exact change), expected effect, cost.
4. Append proposals to `docs/process/improvement-log.md` with status `Proposed`.
5. Present them to the user. Apply only those the user approves; mark them `Applied` or `Rejected`.

## Safety constraints
- Never weaken a security, tenant or approval rule on efficiency grounds alone; such proposals are `APPROVAL` and must state the risk.
- Prefer editing an existing skill/rule over adding a new one. New agents need strong evidence of a distinct responsibility.

## Expected output
Numbered proposals with evidence, plus a one-line summary of the system's health.

## Verification
Each proposal cites at least one change record or file. No `.claude/` file changed without explicit user approval in this session.
