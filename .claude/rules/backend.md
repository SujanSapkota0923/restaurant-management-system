---
paths:
  - "backend/**"
---

# Backend rules

Conventions: `docs/conventions/backend.md`, `docs/conventions/api.md`.

- Layering: request handler (auth, parse, respond) → service (business rules, transaction, audit) → data access (tenant-scoped). Handlers contain no business rules.
- Every handler declares its permission; every service that mutates tenant data takes the acting membership explicitly.
- Serializers/schemas allow-list writable fields. No "all fields" write serializers.
- Business commands (`cancel`, `pay`, `mark_ready`) are explicit endpoints, not writable status fields.
- Wrap multi-step writes in one transaction; write the audit record inside it.
- Raise domain errors; map them to the standard error envelope in one place.
- No network calls or slow work inside request transactions; use background jobs with explicit tenant context.
- Never log request bodies of auth endpoints, tokens, passwords or personal data.
