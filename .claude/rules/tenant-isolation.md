# Tenant isolation rules (always apply)

Tenancy strategy and the sanctioned data-access path are defined in `docs/architecture/tenancy.md`. Follow it; these rules state what must never happen.

- Tenant context is resolved server-side on every request from the restaurant in the URL path, validated against the user's active memberships (or the device session's bound restaurant) — never from a request body, query string or header (ADR-0003/0006).
- Every read/write of tenant-owned data goes through the tenant-scoped access path. No unscoped managers/repositories, no raw queries on tenant tables outside it.
- Tenant-owned tables carry the tenant key and database-level protection (RLS or the ADR's equivalent). New tenant tables get it in the same migration.
- Related-object IDs from the client are looked up within the current tenant. Another tenant's ID returns 404 — never 403, never the object.
- Cache keys, storage paths, realtime channels, job payloads, search indexes and log context include the tenant ID. Background jobs re-establish tenant context before querying.
- Per-restaurant uniqueness (table numbers, SKUs, role names) is unique within the tenant.
- Platform/superuser cross-tenant access is a separate audited path, never a flag on tenant endpoints.
- Every endpoint touched has a cross-tenant negative test.
- Any change to tenant resolution, RLS or cross-tenant capability is `APPROVAL`.
