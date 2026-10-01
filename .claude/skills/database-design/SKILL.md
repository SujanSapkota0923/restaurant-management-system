---
name: database-design
description: Design or review RMS relational schema — tables, types, keys, constraints, indexes, tenant keys, transactions, locking, concurrency, history/snapshots, soft deletion and query performance. Use when a change adds or alters persistent data or a data-heavy query. Module-agnostic.
---

# database-design

## Purpose
Keep data correct under concurrency and over years of history, and keep tenant-scoped queries fast.

## When to use
- New/changed table or column; new list/report query; a race condition.

## When NOT to use
- Migration mechanics — see `migration-safety`. Domain ownership questions — see `domain-modeling` first.

## Inputs
- Domain model and invariants; `docs/architecture/data.md`; `docs/architecture/tenancy.md`; existing schema.

## Procedure
1. **Tenant ownership.** Tenant-owned table? Then it follows `tenancy.md` exactly (tenant key column, RLS policy, tenant-composite foreign keys, tenant-leading indexes).
2. **Keys and types.** Stable surrogate primary keys; never expose sequential IDs if the ADR says not to. Money: fixed-precision decimal or integer minor units per ADR — never float. Quantities: decimal with explicit scale. Timestamps: timezone-aware UTC.
3. **Constraints.** Encode invariants: `NOT NULL`, `CHECK` (non-negative amounts, valid state values), `UNIQUE` (including partial unique, e.g. one open order per table if required), FKs with deliberate `ON DELETE` (default `RESTRICT`/`PROTECT` for business data).
4. **History.** Snapshot values that must not change retroactively (prices, tax rates, names on receipts). Prefer append-only records for ledgers (payments, stock movements).
5. **Deletion.** Hard delete by default for non-business data; soft delete (deactivate) only when the record is referenced by history or must be restorable — document why. Soft-deleted rows must not leak into active queries.
6. **Transactions and concurrency.** Name each multi-row operation's transaction boundary. Choose: DB constraint, row lock (`SELECT … FOR UPDATE`), optimistic version column, or idempotency key. State which race each prevents.
7. **Indexes.** One per real access path; leading column is the tenant key for tenant-scoped queries. Check list/report queries with `EXPLAIN` on realistic volumes.
8. **N+1 and pagination.** Every list endpoint is paginated and loads relations deliberately.

## Safety constraints
- No schema for unconfirmed requirements.
- No raw SQL built from strings; parameterize always.

## Expected output
Schema proposal (tables, columns, constraints, indexes) with the invariant or access path each serves, plus transaction/concurrency notes.

## Verification
Each invariant from the domain model has an enforcement point; each index has a query; each race has a named prevention and a test in the plan.
