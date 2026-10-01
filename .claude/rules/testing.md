---
paths:
  - "**/tests/**"
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/*.test.*"
  - "**/*.spec.*"
---

# Testing rules

Strategy: `docs/process/testing-strategy.md`. Procedure: `testing` skill.

- Every behavior change ships with tests; every bug fix ships with a regression test that failed before the fix.
- Protected endpoints have negative tests: 401, 403, cross-tenant 404, invalid input, invalid state.
- Integration tests use the production database engine and at least two tenants.
- Never mock the authorization or tenant layer in tests that verify them.
- Never skip, delete or weaken an existing test to get green without approval in the change record.
- Fake data only. No real personal data, no secrets, no production dumps.
- Deterministic: frozen time, seeded randomness, no sleeps for synchronization.
