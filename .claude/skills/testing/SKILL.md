---
name: testing
description: Plan and write RMS automated tests — unit, integration, API, authorization, tenant-isolation, workflow, regression and concurrency — with negative cases first-class and acceptance criteria traced to tests. Use whenever behavior is added or changed, or a bug is fixed.
---

# testing

## Purpose
Prove behavior, including what must *not* happen.

## When to use
- Implementation and Testing gates; every bug fix (regression test first).

## When NOT to use
- Manual exploratory checks only — those supplement, never replace.

## Inputs
- Acceptance criteria, threat-model required tests, `docs/process/testing-strategy.md`.

## Procedure
1. **Trace.** Table: acceptance criterion → test name(s).
2. **Choose the level** (lowest that proves it): pure logic → unit; DB constraints, transactions, permissions, tenant scoping → integration against a real database (same engine as production); request/response contract → API test; multi-step user journey → workflow/E2E (few, critical paths only).
3. **Mandatory negatives** per protected endpoint: 401, 403, cross-tenant 404, invalid input 400/422, invalid state transition 409, replay/duplicate (idempotency) where applicable.
4. **Concurrency** where the design names a race: run operations in parallel transactions/threads and assert invariants (no oversell, no double payment, no duplicate order).
5. **Regression.** For a bug: write the failing test first, then fix, then show it passes.
6. **Data.** Factories/fixtures with fake data; two tenants by default in integration tests.
7. **Determinism.** Freeze time, seed randomness, no sleeps for sync, no order-dependent tests.
8. **Run** the affected suites and report exact commands and counts.

## Safety constraints
- Never skip, delete, or weaken an existing test to get green without approval.
- Never mock the authorization or tenant layer in tests meant to verify it.

## Expected output
Tests + traceability table + run results in the change record.

## Verification
All criteria traced; negatives present; suites run with results quoted.
