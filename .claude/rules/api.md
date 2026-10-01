---
paths:
  - "backend/**/urls.py"
  - "backend/**/views*.py"
  - "backend/**/viewsets*.py"
  - "backend/**/api/**"
  - "backend/**/serializers*.py"
  - "backend/**/schemas*.py"
  - "frontend/**/api/**"
---

# API rules

Full conventions: `docs/conventions/api.md`. Design procedure: `api-design` skill.

- All endpoints are versioned under the prefix fixed in `api.md`.
- Errors use the standard envelope with a stable machine `code`, human `message`, optional `fields`, and `request_id`.
- Other tenants' resources return 404. Unauthenticated 401, lacking permission 403, invalid state 409, validation 400.
- Lists are paginated with a bounded maximum page size.
- Retry-able creates for orders/payments accept an `Idempotency-Key` header.
- Concurrency-sensitive updates require a version and return 409 on mismatch.
- Breaking changes (remove/rename field, change meaning or status code) are `APPROVAL`.
- Update the API reference in the same change.
