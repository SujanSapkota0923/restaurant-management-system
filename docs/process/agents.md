# Agents and Responsibilities

Definitions live in `.claude/agents/`. All agents follow `agent-contract.md`. Rationale: ADR-0001.

| Agent | Owns (gates) | Writes | Can block? | Preloaded skills |
|-------|--------------|--------|-----------|------------------|
| **Orchestrator** (main session) | Request, Acceptance; runs all gates; asks the human | Change records, final report | — | `change`, `retro` (invoked) |
| `requirements-analyst` | Requirements | Change record; confirmed rules in `requirements.md` | No | requirements-analysis |
| `architect` | Impact analysis, Architecture, API contract | Change record, `docs/architecture/`, ADRs | Raises risk level | impact-analysis, domain-modeling, api-design |
| `data-engineer` | Data design, migration plan | Change record, `data.md`; migrations when asked | Flags `APPROVAL` | database-design, migration-safety, tenant-isolation |
| `security-engineer` | Security analysis, Security review | Change record, `security.md`, `risks.md` | **Yes (`BLOCK`)** | threat-modeling, review-security, tenant-isolation, access-control, secure-coding |
| `ux-designer` | UX flow design; UI review | Change record, `ux-principles.md` | No | mobile-first-ux |
| `backend-engineer` | Implementation (server) | Backend code + tests | Reports `BLOCKED` | secure-coding, tenant-isolation, access-control, audit-logging, testing |
| `frontend-engineer` | Implementation (client) | Frontend code + tests | Reports `BLOCKED` | mobile-first-ux, secure-coding, testing |
| `qa-engineer` | Testing | Tests only | Reports failing tests | testing, tenant-isolation |
| `code-reviewer` | Code review | Nothing (read-only) | `CHANGES REQUESTED` | review-code |
| `tech-writer` | Documentation | Docs, changelog, ADR status | No | documentation |

## Conflict resolution
1. Security/tenant/authorization concerns from `security-engineer` win over convenience, UX speed or delivery time, unless the human accepts the risk.
2. Accepted ADRs win over agent preference.
3. Otherwise the orchestrator states both positions and the trade-off, recommends one, and decides (`REVIEW`) or asks the human (`APPROVAL`).

## Why not more agents
- Orchestrator is not a subagent: subagents cannot delegate or ask the user.
- Security analysis and security review share one agent: same knowledge; independence from the implementer is preserved.
- Deployment/DevOps agent: deferred until Phase 2/10 has real infrastructure. Until then the architect and security engineer cover deployment decisions.
- Performance: covered by `data-engineer` (queries) and `frontend-engineer`; revisit via `retro`.
