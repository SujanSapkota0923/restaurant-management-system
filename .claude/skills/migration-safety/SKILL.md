---
name: migration-safety
description: Plan, write and review RMS database migrations so they are reversible where possible, safe under live traffic, correct for every tenant, and never destroy data without approval. Use for any migration file or data backfill.
---

# migration-safety

## Purpose
Change schema and data without downtime surprises or data loss.

## When to use
- Creating or reviewing any migration or data backfill.

## When NOT to use
- Designing the target schema — `database-design` first.

## Inputs
- Current and target schema; data volumes (estimate if unknown and say so); `docs/architecture/tenancy.md`.

## Procedure
1. **Classify** each operation: additive (safe), constraining (may fail on existing data), destructive (drop/rename/narrow/rewrite). Destructive = `APPROVAL`.
2. **Expand → migrate → contract.** Add new structures first, deploy code that writes both/reads new, backfill, then remove old structures in a later, separately approved change.
3. **Locks.** Avoid long table locks: add columns nullable or with non-volatile defaults, create indexes concurrently where supported, add constraints as `NOT VALID` then validate separately, batch large backfills.
4. **Tenant coverage.** The migration must apply correctly for all tenants and new tenants. New tenant-owned tables include RLS policy in the same migration.
5. **Reversibility.** Provide a reverse migration or state explicitly why it is irreversible and what the recovery path is (backup restore point).
6. **Data backfills.** Idempotent, batched, resumable, logged counts; never in the same transaction as a long schema change.
7. **Test.** Run forward and backward on a local database with representative data, including edge rows (nulls, soft-deleted rows, max lengths).

## Safety constraints
- Never run migrations against shared, staging or production databases from an agent session.
- Never combine a destructive step with other steps in one migration.
- Never drop data "because it looks unused" — prove it and get approval.

## Expected output
Migration plan: steps, classification, lock impact, reversibility, backfill plan, deploy ordering relative to code.

## Verification
Forward + reverse ran locally (quote commands and output); RLS present on new tenant tables; destructive steps have recorded approval.
