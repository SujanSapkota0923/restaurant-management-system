# Development Workflow and Gates

Every change flows through gates. The orchestrator (main session, `change` skill) owns the flow; agents own individual gates. Which gates run depends on the risk level in `risk-and-approval.md`.

## Gate sequence

| # | Gate | Owner | Output (written into the change record) | Skipped at |
|---|------|-------|------------------------------------------|------------|
| 1 | Request | orchestrator | Restated request, initial risk level | — |
| 2 | Requirements | `requirements-analyst` | Goals, acceptance criteria, edge/failure cases, open questions | L0 |
| 3 | Impact analysis | `architect` | Affected modules, data, APIs, permissions, UI, docs; risk confirmed/raised | L0, L1 |
| 4 | Architecture | `architect` (+ `data-engineer` if data changes) | Design decision, ADR if the decision is lasting | L0, L1 |
| 5 | Security analysis | `security-engineer` | Threat model / checklist, required controls, verdict | L0, L1 |
| 6 | Design | `data-engineer`, `ux-designer`, `architect` as needed | Schema/migration plan, API contract, UX flow | L0 |
| 7 | Implementation | `backend-engineer`, `frontend-engineer` | Code + tests, list of files changed | — |
| 8 | Testing | `qa-engineer` | Test plan executed, results, gaps | L0 |
| 9 | Security review | `security-engineer` | Findings, `PASS` / `PASS WITH RISKS` / `BLOCK` | L0, L1 |
| 10 | Code review | `code-reviewer` | Findings, requirement traceability, `APPROVE` / `CHANGES REQUESTED` | L0 |
| 11 | Documentation | `tech-writer` | Docs and changelog updated | L0 (unless docs were the change) |
| 12 | Acceptance | orchestrator + human for L3 | Final report | — |

## Gate rules

- A gate passes only when its output is written into the change record. "Looks fine" is not an output.
- Open questions from gate 2 that affect behavior must be answered by the human before gate 7. Questions that do not affect behavior may be deferred and listed in the report.
- L3 changes stop for human approval after gate 6 (design approved) and at gate 12 (accept).
- Any `APPROVAL`-class decision stops the flow at the point it is discovered, whatever the gate.
- Failing review gates (8–10) send work back to gate 7. After two round-trips on the same finding, the orchestrator stops and asks the human.
- If implementation reveals the design was wrong, return to the gate that owns the wrong decision; do not patch around it.
- Gates 2–6 produce documents and decisions, not production code.

## Parallelism

Independent gates may run in parallel when their inputs are ready:
- Gate 5 (security analysis) and gate 6 UX design can run alongside data design once gate 4 is done.
- Backend and frontend implementation can run in parallel once the API contract is fixed.
- Gates 9 and 10 run in parallel.

## Change records

Every L1+ change has a record at `docs/changes/NNNN-short-slug.md` created from `docs/changes/_template.md`. It is the task state: a future session resumes work by reading it. When a change is accepted, set its status to `Done`; do not delete records.

## Definition of done

- Acceptance criteria met and traced to tests.
- Negative tests exist for every permission and tenant boundary touched.
- Security review passed (L2+).
- Code review approved.
- Docs, ADRs and changelog updated.
- Final report delivered, including what was intentionally not changed and unresolved risks.
