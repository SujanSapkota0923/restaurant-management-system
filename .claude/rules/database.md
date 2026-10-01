---
paths:
  - "backend/**/models.py"
  - "backend/**/models/**"
  - "backend/**/migrations/**"
  - "**/*.sql"
  - "scripts/db/**"
---

# Database rules

Design guidance: `database-design` skill, `docs/architecture/data.md`.

- Money is never a float. Use the representation fixed in `docs/architecture/data.md`.
- Enforce invariants with constraints (`NOT NULL`, `CHECK`, `UNIQUE`, FKs) as well as in services.
- Business-data foreign keys default to restrict/protect on delete. Cascades need a written reason.
- Snapshot values that must not change retroactively (price, tax rate, item name at order time).
- Ledgers (payments, stock movements, audit) are append-only; corrections are new rows.
- Soft delete only where history references the row or restore is required; document why on the model.
- Every list query is tenant-scoped, paginated, and backed by a tenant-leading index.
- Contended updates use a named strategy (constraint, row lock, version column or idempotency key) with a test.
