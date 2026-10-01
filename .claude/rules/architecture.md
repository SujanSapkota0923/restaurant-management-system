# Architecture rules (always apply)

- Read `docs/architecture/overview.md` and relevant ADRs before changing structure. `Accepted` ADRs are binding; to deviate, propose a superseding ADR (`APPROVAL`).
- Respect bounded-context ownership in `docs/architecture/domain-model.md`. A context changes another context's data only through that context's service interface, never by writing its tables directly.
- Business rules live in the domain/service layer — not in views, serializers, UI components or database triggers. DB constraints that enforce invariants are welcome.
- State transitions are explicit commands with guarded state machines, not free writes to a `status` field.
- Multi-step business writes run in one transaction; no partial state on error.
- No new service, datastore, framework or bounded context without an ADR and approval.
- Prefer the simplest design that meets confirmed requirements. No speculative abstraction, plugin systems, or config for hypothetical needs.
