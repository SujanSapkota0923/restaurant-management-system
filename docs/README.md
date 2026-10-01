# RMS Documentation Map

Single source of truth for humans and agents. Each page has one owner; update the owning page, don't duplicate facts elsewhere.

| Page | What it holds | Owner |
|------|---------------|-------|
| **Product** | | |
| `product/requirements.md` | Confirmed rules + open questions | requirements-analyst |
| `product/briefs/` | Per-area requirement briefs (acceptance criteria, edge cases, open questions); Draft until questions answered | requirements-analyst |
| `product/ux-principles.md` | Binding UX principles | ux-designer |
| `product/ux-flows.md` | Navigation model and core UX flows (Proposed) | ux-designer |
| `product/roadmap.md` | Phases, status, exit criteria | orchestrator (human approves) |
| **Architecture** | | |
| `architecture/overview.md` | System shape, cross-cutting decisions summary | architect |
| `architecture/domain-model.md` | Vocabulary, bounded contexts, lifecycles | architect |
| `architecture/tenancy.md` | Tenant isolation design | architect + security-engineer |
| `architecture/authorization.md` | Identity/membership/permissions, catalog | security-engineer + architect |
| `architecture/security.md` | Security model, baseline control applicability | security-engineer |
| `architecture/data.md` | Data conventions and integrity rules | data-engineer |
| `architecture/audit-logging.md` | Audit scope and event shape | architect + security-engineer |
| **Conventions** | | |
| `conventions/api.md` | HTTP API conventions | architect |
| `conventions/backend.md` | Backend code conventions | backend-engineer / architect |
| `conventions/frontend.md` | Frontend code conventions | frontend-engineer / ux-designer |
| **Process** | | |
| `process/workflow.md` | Gates and definition of done | orchestrator (changes = `APPROVAL`) |
| `process/risk-and-approval.md` | Risk levels, AUTO / REVIEW / APPROVAL | orchestrator (changes = `APPROVAL`) |
| `process/agent-contract.md` | Rules every agent follows, output format | orchestrator |
| `process/agents.md` | Agent responsibilities | orchestrator |
| `process/skills.md` | Skill registry | orchestrator |
| `process/testing-strategy.md` | Test levels and mandatory suites | qa-engineer |
| `process/operations.md` | CI/CD, deployment, observability (planned) | architect + security-engineer |
| `process/improvement-log.md` | Proposed engineering-system changes | orchestrator |
| **Records** | | |
| `decisions/` | ADRs (`0000-template.md`) | architect / tech-writer |
| `changes/` | Change records = task state (`_template.md`) | orchestrator |
| `risks.md` | Known and accepted risks | security-engineer |
| `legacy/reference-assessment.md` | What `../rms` has; keep / discard | architect |
| `incidents/` | Incident notes (created when needed) | debugging owner |

Status labels used on pages: **Proposed** (not binding), **Accepted** (binding), **Planned** (not built).
