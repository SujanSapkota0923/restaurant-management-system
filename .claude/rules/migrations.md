---
paths:
  - "backend/**/migrations/**"
  - "**/migrations/**"
---

# Migration rules

Procedure: `migration-safety` skill.

- Never edit a migration that has been merged or applied anywhere shared. Write a new one.
- Destructive operations (drop, rename, narrow type, data rewrite) are `APPROVAL` and go in their own migration, separate from additive steps.
- Use expand → migrate → contract across releases for renames and type changes.
- New tenant-owned tables include tenant key, RLS policy and tenant-leading indexes in the same migration.
- Provide a reverse migration, or state in the migration why it is irreversible and what the recovery path is.
- Backfills are batched, idempotent and resumable; not inside long schema-lock transactions.
- Run forward and reverse locally before review. Never run migrations against shared, staging or production databases from an agent session.
