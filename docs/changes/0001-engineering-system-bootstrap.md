# 0001 — Engineering system bootstrap

- **Status:** Done — user said "carry on" (2026-09-30); ADR-0001 remains Proposed until explicitly accepted
- **Risk level:** L3 — defines the process, security rules and approval gates everything else relies on
- **Requested by / date:** product owner, 2026-09-30
- **Current gate:** 12 (Acceptance)

## 1. Request
Design and establish the engineering system (agents, skills, rules, gates, docs, roadmap) for rebuilding RMS, using `../rms` as a reference. Do not build restaurant features.

## 2. Requirements
From the bootstrap brief, sections 1–18. Product rules captured in `docs/product/requirements.md` (Confirmed C1–C5); everything else recorded as open questions Q1–Q25.

## 3. Impact analysis
Greenfield directory `Rms/` (was empty). `../rms` read only, not modified.

## 4. Architecture decision
ADR-0001 (system design), ADR-0002 (rebuild; accepted by brief), ADR-0003..0006 proposed.

## 5. Security analysis
Baseline control applicability table in `docs/architecture/security.md`. Guardrails: `.claude/settings.json` denies reading secret files and destructive git/DB commands; asks before commit/push/migrate.

## 7. Implementation — files created
- `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `.gitignore`, `.claude/settings.json`
- `.claude/agents/` (10), `.claude/skills/` (19), `.claude/rules/` (13)
- `docs/` — product (3), architecture (7), conventions (3), process (8), changes (template + this record), decisions (7 incl. template), legacy (1), risks, map

## Self-review (brief §18)

**Architecture**
- Responsibilities separated; overlaps resolved: architect = domain + architecture; one security agent covers analysis + review (independence from implementers kept).
- Orchestrator could not be a subagent (no nested delegation / no user questions) → main session + `change` skill.
- Missing: DevOps/deployment owner — deliberately deferred (no infrastructure yet); covered by architect + security until Phase 2.

**Skills**
- 17 knowledge + 2 workflow skills; merged topics listed in `docs/process/skills.md`. Stack-specific skills deferred until ADR-0004 is accepted (avoids choosing technology prematurely).
- Fixed during review: `code-review` and `security-review` collided with Claude Code built-in skill names and were shadowed → renamed `review-code` and `review-security`.

**Security**
- Agents cannot legitimately bypass authz/tenancy: forbidden in agent contract, rules, and every relevant skill; security engineer can `BLOCK`.
- Secrets: read-deny in settings, `secrets.md` rule, `.gitignore`, review secret scan.
- Destructive operations: settings deny/ask + `APPROVAL` class + migration rules.
- Residual: subagents may not auto-load `.claude/rules/`; fixed by making the agent contract require reading applicable rules (step 3a).
- Residual: agent write-scope limits (e.g. "docs only") are instructions, not enforced permissions — acceptable now; revisit via `retro`.

**Workflow**
- Request → production path defined with L0–L3 levels, escalation triggers, AUTO/REVIEW/APPROVAL, L3 double approval, security veto.
- Change records carry task state across sessions.

**Maintainability**
- Future sessions start from `CLAUDE.md` → `docs/README.md`. `retro` + improvement log let the system evolve with review.

## 12. Acceptance / final report
- Intentionally not changed: `../rms` (read only). No application code, no schemas, no technology locked in.
- Follow-ups:
  - Path globs in `.claude/rules/{backend,frontend,api,database,migrations}.md` assume `backend/` and `frontend/` directories; adjust when the Phase 2 scaffold fixes the layout.
  - Initialise Git and a remote (not done: directory is not a repository; commits need your go-ahead).
  - Exercise the system on the first Phase 2 change, then run `/retro`.
- Human approvals needed: acceptance of this system; ADR-0001, 0003, 0004, 0005, 0006; blocking open questions.
