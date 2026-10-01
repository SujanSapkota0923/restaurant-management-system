# Agent Contract

Every RMS agent (and the main session) follows this contract. Agent definitions in `.claude/agents/` add role-specific duties on top of it; they never relax it.

## Before acting

1. Read the change record you were given (`docs/changes/NNNN-*.md`). If none was given for L1+ work, say so and stop.
2. Read the docs relevant to your role (listed in your agent file) and the code you will touch. Understand the current architecture before proposing changes to it.
3. Check `docs/decisions/` for ADRs that constrain your work. `Accepted` ADRs are binding; `Proposed` ADRs are not.
3a. Read the project rules in `.claude/rules/` that apply to the files you will touch (always-on rules have no `paths:` header; path-scoped ones list their globs). Do not assume they were loaded for you.

## While acting

4. Separate **facts** (verified in code/docs, cite `path:line`) from **assumptions** (label them `ASSUMPTION:`).
5. Never invent a business rule. If requirements do not cover a case, record an open question.
6. Stay in scope. No unrelated refactors, renames, formatting sweeps or "while I'm here" fixes. Note them as follow-ups instead.
7. Prefer small, reviewable changes. One concern per change.
8. Preserve backward compatibility unless the change record explicitly approves a break.
9. For every change, consider: failure states, security, authorization, tenant isolation, data migration, performance, auditability.
10. Add or update tests with every behavior change, including negative cases.
11. Update docs when architecture or behavior changes.
12. Classify each decision you take as `AUTO`, `REVIEW` or `APPROVAL` (`docs/process/risk-and-approval.md`). On `APPROVAL`: stop and return it as a question. You cannot ask the user yourself; the orchestrator will.

## Never

- Weaken, bypass, mock out or comment out an authorization check, tenant filter, RLS policy, CSRF protection, validation or audit call to make something work or a test pass.
- Read, print or copy secrets or `.env` files.
- Run destructive commands (dropping data, force-push, hard reset) or apply migrations against any shared/production database.
- Modify `.claude/`, `CLAUDE.md` or process docs unless the change record is specifically about them and approved.
- Copy code from `../rms` without the change record approving that specific reuse.

## Output format

End every response with:

```
## Result
Status: DONE | BLOCKED | NEEDS APPROVAL | PASS | PASS WITH RISKS | BLOCK | APPROVE | CHANGES REQUESTED
Changed: <files or "none">
Intentionally not changed: <items>
Facts / assumptions: <key ones>
Decisions: <decision — AUTO/REVIEW/APPROVAL>
Open questions: <numbered, blocking/non-blocking>
Risks: <unresolved>
Verification: <commands run and results, or "not run" with reason>
```

Do not claim a test passed or a file changed unless you ran or changed it in this task.
