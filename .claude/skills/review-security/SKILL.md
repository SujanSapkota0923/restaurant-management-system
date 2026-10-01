---
name: review-security
description: Independent, OWASP-oriented security review of an RMS diff — authentication, authorization, tenant isolation, input/output handling, secrets detection, dependency vulnerabilities, API abuse, uploads, webhooks, logging and configuration. Use at the Security Review gate after implementation and before acceptance.
---

# review-security

## Purpose
Catch vulnerabilities in the actual code before it ships.

## When to use
- Security Review gate for L2+ changes; periodic whole-repo sweeps; before a release.

## When NOT to use
- Pre-design threat analysis — `threat-modeling`.

## Inputs
- The diff (e.g. `git diff <base>...HEAD`), the change record's threat model, `docs/architecture/security.md`.

## Procedure
1. **Scope.** List changed files; mark those touching auth, permissions, tenant data, money, uploads, webhooks, config.
2. **Controls from threat model.** Verify each required control is implemented and tested. Missing control = finding.
3. **Authorization & tenancy.** For every endpoint/command in the diff: permission declared? tenant-scoped access? object-level checks? cross-tenant negative test present? (see `access-control`, `tenant-isolation`).
4. **Checklist pass.** Walk `secure-coding` against the diff.
5. **Secrets scan.** Search the diff and new files for keys, tokens, passwords, private keys, connection strings, `.env` content. Use a scanner if installed (e.g. `gitleaks detect --no-git -s .` or `gitleaks protect --staged`); otherwise grep for high-signal patterns (`AKIA`, `-----BEGIN`, `sk_live`, `password=`, `secret=`, `token=`).
6. **Dependencies.** For changed manifests run the ecosystem auditor if available (`pip-audit`, `npm audit --omit=dev`); report known-vulnerable versions and new transitive risk.
7. **Configuration.** Debug, CORS, CSRF, cookies, allowed hosts, headers — any changes?
8. **Logging.** New logs leak personal data, tokens or bodies?
9. **Abuse.** New unauthenticated or expensive endpoints rate-limited and bounded?

## Findings format
`[severity] path:line — issue — exploit scenario — fix`. Severity: critical (cross-tenant access, auth bypass, secret leak, RCE), high, medium, low.

## Verdict
- `BLOCK`: any critical, or any high without an agreed fix.
- `PASS WITH RISKS`: only medium/low, each listed for `docs/risks.md` if accepted.
- `PASS`: no findings of medium or above.

## Safety constraints
- Do not run exploit attempts against anything except local test environments.
- Do not paste discovered secrets into the report; cite file and line and say "secret-like value".

## Verification
State which tools ran (with commands) and which were unavailable.
