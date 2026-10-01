---
name: threat-modeling
description: Threat-model an RMS change or component before implementation — assets, actors, trust boundaries, entry points, STRIDE and OWASP API Top 10 threats, abuse cases, required controls and required negative tests. Use at the Security Analysis gate for L2+ changes. Feature-agnostic.
---

# threat-modeling

## Purpose
Decide the security controls while the design can still change cheaply.

## When to use
- Security Analysis gate (L2 lightweight, L3 full).

## When NOT to use
- Reviewing written code — use `review-security`.

## Inputs
- Requirements, design, `docs/architecture/security.md`, `docs/risks.md`.

## Procedure
1. **Assets:** what is valuable (tenant data, money state, credentials, personal data, audit trail, availability during service hours).
2. **Actors:** anonymous internet, customer (if customer surfaces exist), staff of same tenant with fewer permissions, staff of another tenant, former staff, owner, platform operator, compromised dependency.
3. **Entry points and trust boundaries:** endpoints, uploads, webhooks, background jobs, realtime channels, admin tools.
4. **Threats per entry point** — walk:
   - Spoofing: session theft, fixation, credential stuffing, enumeration
   - Tampering: mass assignment, amount/price manipulation, state-machine skipping, replay
   - Repudiation: missing or forgeable audit
   - Information disclosure: IDOR/BOLA, cross-tenant leaks, verbose errors, logs, caches
   - Denial of service: unbounded queries, missing rate limits, expensive reports during service
   - Elevation: permission escalation, role self-grant, platform-path misuse
   - Plus as applicable: XSS, CSRF, SSRF, unsafe deserialization, malicious uploads, webhook forgery/replay, race conditions
5. **Controls:** for each credible threat, the control and where it lives. Prefer controls already standard in `security.md`.
6. **Tests:** each control gets a negative test for the QA plan.
7. **Residual risk** and verdict: `PROCEED` / `PROCEED WITH CONTROLS` / `BLOCK`.

## Safety constraints
- Do not mark a threat "not applicable" without a one-line reason.

## Expected output
Threat table (entry point, threat, likelihood/impact, control, test) in the change record.

## Verification
Every control maps to an acceptance criterion or test; every `L3` threat model names at least the tenant, permission and replay/race threats.
