---
name: tenant-isolation
description: Design, implement, test and review tenant isolation in RMS so no restaurant can read or change another restaurant's data through IDs, crafted requests, bypassed UI, caches, files, events, jobs or misconfigured permissions. Use for any code that reads or writes tenant-owned data, and in every security review.
---

# tenant-isolation

## Purpose
Make cross-tenant access impossible by construction, with defense in depth.

## When to use
- Any new query, endpoint, background job, cache, file storage path, realtime channel, export or report over tenant data.
- Every L2+ security review.

## When NOT to use
- Platform-level (non-tenant) data such as the tenant registry — but those paths need their own `APPROVAL` review.

## Inputs
- `docs/architecture/tenancy.md` (the chosen strategy — follow it, not this file, when they differ); the code under change.

## Procedure — building
1. **Resolve tenant server-side** on every request from the restaurant in the URL path, validated against the user's active memberships (device sessions: must equal the bound restaurant, else 409). Never from body, query string or header. See ADR-0003/0006.
2. **Scope every query** through the sanctioned tenant-scoped data access path defined in `tenancy.md`. No raw unscoped access to tenant tables.
3. **Database layer**: tenant-owned tables have RLS (or the ADR's equivalent) so a missing app filter still returns nothing.
4. **References**: foreign keys between tenant-owned rows must not be able to point across tenants (tenant-composite keys or validation in the same transaction).
5. **Lookups by ID** always include tenant scope; cross-tenant IDs return 404.
6. **Side channels**: cache keys, file/object storage paths, realtime channels, queue payloads, search indexes and log context all carry tenant ID; background jobs re-establish tenant context explicitly before any query.
7. **Uniqueness** constraints that are per-restaurant (table number, SKU) are unique *within* tenant, not globally.

## Procedure — testing (mandatory for each endpoint touched)
- Two tenants A and B with overlapping data. As a user of A: list, retrieve, update, delete and command endpoints using B's IDs → 404/no effect, B's data unchanged.
- A user with membership in A only, crafting a request to B's tenant context → denied.
- A query executed without tenant context → returns nothing / raises (RLS test).
- Background job for A never touches B's rows.

## Procedure — reviewing
Search the diff for: unscoped ORM managers, raw SQL, `.objects.all()`/equivalent on tenant models, IDs taken from request body for related objects, cache/storage keys without tenant, jobs without tenant context, platform-bypass flags.

## Safety constraints
- Never disable RLS or use a bypass role in application request paths.
- Superuser/platform access is a separate, audited path; never a flag on normal endpoints.

## Expected output
Implementation that follows the path above, plus the isolation tests; in reviews, findings with `path:line`.

## Verification
The isolation tests above exist and pass for every endpoint touched.
