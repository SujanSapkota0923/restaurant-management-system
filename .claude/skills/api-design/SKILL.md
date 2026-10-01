---
name: api-design
description: Define or review RMS HTTP API contracts — resource shape, methods, status codes, error format, pagination, filtering, idempotency, versioning, and the permission each endpoint requires. Use when adding or changing an endpoint.
---

# api-design

## Purpose
Consistent, predictable, secure APIs that frontend and tests can rely on.

## When to use
- New or changed endpoint; new client integration.

## When NOT to use
- Internal function signatures inside one module.

## Inputs
- Requirements, domain model, `docs/conventions/api.md`, existing endpoints in the same context.

## Procedure
1. Pick resource vs command endpoint. CRUD on a resource uses standard methods; business transitions use explicit commands (`POST /orders/{id}/cancel`), not a writable `status` field.
2. For each endpoint write: method + path, required permission code, request schema (allow-listed writable fields, types, limits), response schema, status codes, error codes.
3. Tenant context comes from the restaurant in the URL path (`/api/v1/r/{tenant_id}/...`, see `api.md`), validated against the caller's memberships — never from a tenant ID in the body, query string or header.
4. List endpoints: pagination mandatory, bounded page size, documented filters and ordering, tenant-scoped.
5. Retry-able mutations that create money or orders accept an idempotency key.
6. Concurrency-sensitive updates carry a version/ETag and return a conflict error on mismatch.
7. Errors use the standard error envelope from `api.md`; never leak stack traces, SQL, or whether a resource exists in another tenant (return 404, not 403, for other tenants' IDs).
8. Breaking change? It is `APPROVAL`; propose a compatible alternative first.

## Safety constraints
- No endpoint without a permission. `AllowAny` endpoints need an explicit threat model entry.
- No mass assignment: never bind request bodies to all model fields.

## Expected output
An endpoint table in the change record's Design section, and updates to the API reference when implemented.

## Verification
Each endpoint has permission, schema, errors, and a matching negative test listed in the test plan.
