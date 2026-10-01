# ADR-0001 — Agent-based engineering system on Claude Code

- **Status:** Proposed (awaiting human review of the bootstrap)
- **Date:** 2026-09-30
- **Deciders:** product owner; proposed by bootstrap session
- **Change record:** docs/changes/0001-engineering-system-bootstrap.md

## Context
RMS will be built and maintained mostly through Claude Code. One general-purpose agent tends to skip requirements, mix concerns and self-approve. The brief asks for specialised agents, reusable skills, gates and human approval points.

Claude Code constraints that shape the design (as of this date): subagents cannot spawn subagents and cannot ask the user questions; skills are loaded on demand by name/description; `.claude/rules/*.md` load always or by path glob; settings can deny tool access.

## Options considered
1. **Orchestrator as a subagent** — cannot delegate further or ask the user; unusable.
2. **Main session as orchestrator + 10 specialist subagents + skills** — fits the platform.
3. **Twelve agents exactly as in the brief** — "Authorization/Security" and "Security Review" would share the same knowledge; "Orchestrator" cannot be a subagent.

## Decision
Option 2.
- Orchestrator = main session, driven by `CLAUDE.md` and the `change` skill.
- Agents: `requirements-analyst`, `architect` (domain + architecture), `data-engineer`, `security-engineer` (design-time analysis **and** post-implementation review, with veto), `ux-designer`, `backend-engineer`, `frontend-engineer`, `qa-engineer`, `code-reviewer`, `tech-writer`.
- Security review stays independent of implementation because implementers and the security engineer are different agents with fresh context; merging design-time and review-time security into one agent avoids duplicating the security knowledge base.
- Knowledge in skills (`docs/process/skills.md`); hard constraints in rules; process in `docs/process/`; task state in change records.

## Consequences
- Positive: small system, clear ownership, gates enforceable, state survives sessions.
- Negative: main-session discipline matters — if it implements directly, gates are skipped. Mitigated by `CLAUDE.md` and the risk table.
- Follow-ups: stack-specific skills after ADR-0004; deployment/CI/observability skills in Phase 2/10; `retro` after each phase.

## Revisit when
Claude Code gains nested delegation or user-questions from subagents; or `retro` shows an agent consistently idle or overloaded.
