# Skill Registry

Skills live in `.claude/skills/<name>/SKILL.md`. Each has: purpose, when to use, when not, inputs, procedure, safety constraints, expected output, verification.

## Workflow skills (invoked by the main session)
| Skill | Purpose |
|-------|---------|
| `change` | Orchestrate a change through risk classification, gates, approvals and report |
| `retro` | Propose improvements to the engineering system from evidence (manual only) |

## Knowledge skills
| Skill | Used by | Covers (merged topics) |
|-------|---------|------------------------|
| `requirements-analysis` | requirements-analyst | requirements, edge cases, failure cases |
| `impact-analysis` | architect, orchestrator | architecture analysis, blast radius, risk confirmation |
| `domain-modeling` | architect | bounded contexts, aggregates, invariants, state machines, events |
| `api-design` | architect, backend | contracts, errors, pagination, idempotency, versioning |
| `database-design` | data-engineer | schema, constraints, indexes, concurrency, history, soft delete, query performance |
| `migration-safety` | data-engineer, backend | migrations, backfills, reversibility, locks |
| `tenant-isolation` | security, data, backend, QA | multi-tenancy build/test/review |
| `access-control` | security, backend | authentication + authorization design, enforcement, test matrix |
| `threat-modeling` | security | pre-implementation threat analysis |
| `secure-coding` | backend, frontend, security | implementation checklist (OWASP classes, secrets, uploads, webhooks, rate limits, logging) |
| `review-security` | security | OWASP-oriented diff review, secret detection, dependency audit |
| `mobile-first-ux` | ux-designer, frontend | mobile-first UX + accessibility |
| `testing` | QA, backend, frontend | unit/integration/API/authz/tenant/regression/concurrency |
| `review-code` | code-reviewer | independent review procedure |
| `documentation` | tech-writer | docs, ADRs, changelog |
| `debugging` | orchestrator, engineers | debugging + incident analysis |
| `audit-logging` | backend, security | what/how to audit |

## Deliberately not created yet
| Topic from brief | Where it lives now | Create a skill when |
|------------------|--------------------|---------------------|
| Django/backend development | `docs/conventions/backend.md` | ADR-0004 accepted (Phase 2 scaffold) |
| Frontend development | `docs/conventions/frontend.md` | ADR-0004 accepted |
| Accessibility | inside `mobile-first-ux` | Accessibility work grows beyond the checklist |
| Integration / regression testing | inside `testing` | — (merged on purpose) |
| Performance analysis / query optimisation | inside `database-design`; frontend conventions | `retro` shows repeated perf work |
| Dependency auditing / secret detection | inside `review-security` + `secrets` rule | CI tooling exists (Phase 2) |
| Deployment, CI/CD, observability | `docs/process/operations.md` | Phase 2 (CI) and Phase 10 (deploy) have real infrastructure |
| Incident analysis | inside `debugging` | — |

Adding a skill: prefer extending an existing one; a new skill needs a distinct trigger and procedure. Register it here. Changes to skills are `APPROVAL` (they change agent behavior).
