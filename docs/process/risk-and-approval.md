# Risk Classification and Approval

Every change gets a risk level before work starts. The level decides which gates run (see `workflow.md`) and who must approve. When two levels could apply, take the higher one. The orchestrator may raise a level at any gate; lowering a level needs a stated reason in the change record.

## Risk levels

| Level | Name | Typical examples | Gates |
|-------|------|------------------|-------|
| `L0` | Trivial | Typo, comment, doc wording, formatting | Implement → self-check → report |
| `L1` | Low | UI copy, styling, isolated UI behavior with no API change, test-only changes, internal refactor with full test coverage | Requirements (brief) → Implement → Test → Code review → Docs |
| `L2` | Elevated | New or changed endpoint, business rule, schema change (additive), new dependency, background job, new UI workflow | All gates; security analysis may be a short checklist |
| `L3` | Critical | Authentication, sessions, authorization model, permissions, tenant boundary, payments/money, audit log semantics, destructive or data-rewriting migration, uploads, webhooks, cryptography, production infrastructure | All gates, full threat model, security review is blocking, human approval before implementation **and** before acceptance |

### Automatic escalation triggers

Raise to at least `L2` if the change touches any of: a model/schema, a migration, a serializer/validator, an API contract, a background task, a dependency manifest.

Raise to `L3` if the change touches any of: authentication/session code, permission checks or the permission catalog, tenant resolution or tenant-scoped query helpers, RLS policies, money calculation or payment state, audit logging, file upload handling, webhook handling, secret/config loading, CORS/CSRF/cookie settings, deployment configuration.

## Decision classes

Every decision an agent faces is one of:

| Class | Meaning |
|-------|---------|
| `AUTO` | Agent may decide and proceed. Record it in the change record. |
| `REVIEW` | Agent may proceed, but the decision must be surfaced in the final report and checked by the code or security reviewer. |
| `APPROVAL` | Stop. The orchestrator asks the human and waits. No workaround, no "temporary" implementation. |

### `APPROVAL` — always requires explicit human approval

- Destructive migrations: dropping/renaming columns or tables, narrowing types, data rewrites, backfills on production data.
- Any deletion of data outside a user-facing, already-approved delete flow.
- Changes to the permission catalog, role defaults, or the authorization model.
- Authentication or session architecture changes.
- Tenant-boundary changes: tenant resolution, RLS policies, cross-tenant features, platform-admin access.
- Payment behavior: amounts, rounding, tax, refunds, payment state transitions, provider integration.
- Major architecture changes: new bounded context, new service, new datastore, replacing a framework.
- Breaking API changes (removal, rename, semantic change of a field or status code).
- New third-party service that receives tenant or personal data.
- Production infrastructure, secrets rotation, DNS, deploys to production.
- Irreversible external operations (sending email/SMS to real users, charging money, deleting remote resources).
- Changes to `.claude/`, `CLAUDE.md`, this file, or `workflow.md`.
- Accepting an ADR (moving it from `Proposed` to `Accepted`).
- Any new business rule not already written in `docs/product/requirements.md`.

### `REVIEW` — proceed, but surface

- Additive schema changes (new nullable column, new table, new index).
- New dependency (must pass dependency audit).
- Choice between two designs that are equivalent in behavior.
- Performance trade-offs.
- UX decisions within documented UX principles.
- Adding a permission check that makes access *stricter* in a new endpoint.

### `AUTO`

- Naming, file placement within documented conventions.
- Test additions.
- Refactors inside one module that keep public behavior and tests green.
- Doc corrections that make docs match reality.

## Security veto

The `security-engineer` agent may return `BLOCK`. A blocked change cannot proceed to acceptance until the finding is fixed or the human explicitly accepts the risk in writing; the acceptance is recorded in the change record and in `docs/risks.md`.
