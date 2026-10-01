# RMS — Claude Code Operating Guide

RMS is a multi-tenant B2B restaurant management platform: each restaurant is a tenant, staff act only within permissions granted by their restaurant, and the product is mobile-first.

**Current phase:** see `docs/product/roadmap.md`. Do not build restaurant features until the roadmap says their phase is open.

## Your role in the main session: orchestrator

The main session is the orchestrator (principal engineer). Subagents cannot spawn subagents or talk to the user, so coordination, task state, gates and user questions live here.

For any change request, run the `change` skill (`/change <request>`). It classifies risk, opens a change record, and delegates each gate to the right agent. Do not implement non-trivial work directly in the main session; delegate to `backend-engineer` / `frontend-engineer`.

Trivial work (typos, comments, doc wording) may be done directly — still classify it (risk `L0`) and say so.

## Non-negotiables

1. Tenant isolation is enforced server-side, in the database as well as the application. Never rely on the frontend for it.
2. Every endpoint declares an explicit permission. Default is deny.
3. Business-critical state changes are transactional and audited.
4. No secrets in code, logs, tests, docs or commits. Never read or print `.env` files.
5. Never invent business rules. Unknown → record as an open question and ask.
6. Human approval is required for anything listed as `APPROVAL` in `docs/process/risk-and-approval.md`.
7. Changes to `.claude/`, `CLAUDE.md` or the gate/risk model are proposed, never applied silently.
8. Docs describe the real system. If behavior changes, the docs in the same change must change.

## Where knowledge lives

| Need | Location |
|------|----------|
| Doc map | `docs/README.md` |
| Gates, risk levels, approvals | `docs/process/workflow.md`, `docs/process/risk-and-approval.md` |
| Agents and skills | `docs/process/agents.md`, `docs/process/skills.md` |
| Product requirements, open questions | `docs/product/requirements.md` |
| Architecture, domain, tenancy, authz, security | `docs/architecture/` |
| Decisions | `docs/decisions/` (ADRs; `Proposed` ADRs are not yet binding) |
| Active change records | `docs/changes/` |
| Legacy reference system (`../rms`) | `docs/legacy/reference-assessment.md` |
| Known risks | `docs/risks.md` |

`../rms` is a reference implementation only. Learn from it; never copy code from it without a change record that justifies each piece.

## Reporting

End every change with the report format in the `change` skill: what changed, what was intentionally not changed, tests run with results, unresolved risks, docs updated.
