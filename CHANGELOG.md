# Changelog

All notable changes. Format: Added / Changed / Fixed / Security / Removed, with change record numbers.

## Unreleased

### Added
- Repository scaffold, local development and CI: Django 5.2 + DRF backend (`backend/`, uv) with environment-validated settings that refuse unsafe production configuration, `/health/live` and `/health/ready`, the standard JSON error envelope, request IDs, structured JSON logging with secret redaction; React + TypeScript + Vite installable PWA shell (`frontend/`) with a same-origin API client; PostgreSQL 16 via `compose.yaml` with separate `rms_migrator` and non-privileged `rms_app` roles (tests run as the app role); Makefile entry points; GitHub Actions CI (lint, type-check, tests, migration check, deploy check, pip-audit, npm audit, gitleaks, workflow lint) and Dependabot. (Change 0003)
- Phase 1 discovery documentation (documents only, nothing built): five Draft requirement briefs (identity and access, restaurant setup and staff, menu, tables, orders and kitchen); core UX flows and navigation model (Proposed); domain model with lifecycles and invariants; platform threat model v2 with control sets for manager-set passwords, PIN switch (planned) and device sessions; retention principles; risks R11–R24. (Change 0002)
- Product owner decisions C6.1–C6.23 recorded in `docs/product/requirements.md`, including: Nepal first; one tenant = one location; operator-created restaurants and owner invitations; staff accounts created by a manager with a system-generated, show-once temporary password that must be changed at first sign-in and expires after 72 h; manager reset limited to the restaurant's own staff accounts, never owners; no counter/POS device profile in v1 (kitchen display only); platform-wide usernames; permission catalog v1 and default roles approved; existing users cannot be added as staff; no staff email features in v1; audit rules for staff personal data; residual risk R19 accepted. (Change 0002)
- Engineering system bootstrap: operating guide, 10 agents, 19 skills, 13 rules, gates and risk/approval model, documentation structure, proposed ADRs 0001 and 0003–0006, accepted ADR-0002, roadmap. (Change 0001)

### Changed
- ADR-0003, ADR-0004, ADR-0005 and ADR-0006 accepted (0003 and 0006 with amendments). (Change 0002)
- Briefs, UX flows, domain model, authorization, security, data, audit-logging, overview and risk pages synced to C6.15–C6.23: staff are never invited and an existing user cannot be added as staff; staff email is contact information only (no verification, no reset link); answered questions no longer shown as pending. (Change 0002)
