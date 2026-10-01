# Security Model

**Status:** Proposed. Owner: `security-engineer`. The platform-level threat model (Phase 1) is in "Platform threat model" below (v2, re-validated against the Accepted ADR-0003/0005/0006). This page fixes the baseline and how each required control applies to the architecture.

## Assets
Tenant operational data; money state (bills, payments); personal data (staff, customers in reservations); credentials and sessions; audit trail integrity; availability during service hours.

## Baseline controls — applicability to the proposed architecture

| # | Control | Applies? | How (proposed) | Phase |
|---|---------|----------|----------------|-------|
| 1 | Protect admin routes | Yes | No framework admin exposed in production by default; platform console is a separate authenticated, MFA-protected, audited module | 2 |
| 2 | Server-side access control | Yes | `authorization.md` single helper, default deny, route-scan test | 2 |
| 3 | RLS / tenant DB protection | Yes | PostgreSQL RLS, non-owner app role (`tenancy.md`) | 2 |
| 4 | Email verification | Yes | Owners must verify (C6.11). A staff email is contact information only and is never verified in v1 (C6.21); it grants nothing: no reset link, no account email, no invite acceptance, no ownership (SP-09). Tokens are signed or random, expiring and single-use | 2 |
| 5 | Secure password hashing | Yes | Argon2id (or framework default strong hasher); minimum 10 characters plus breached/common password check (C6.12). PINs are hashed with a server-side pepper (PN-05) | 2 |
| 6 | No auth tokens in localStorage | Yes | Server-side session in HttpOnly cookie (ADR-0006) | 2 |
| 7 | Server-side secrets | Yes | Env/secret manager only; nothing in client bundle | 2 |
| 8 | `.env` excluded from Git | Yes | `.gitignore`, `.env.example` only, CI secret scan | 2 |
| 9 | No secrets in logs | Yes | Structured logging with redaction filter; tested | 2 |
| 10 | Parameterized SQL / safe ORM | Yes | ORM only; raw SQL needs review and parameters | 2 |
| 11 | Server-side input validation | Yes | Schema validation per endpoint, allow-listed fields | 2 |
| 12 | XSS prevention | Yes | React auto-escaping, no raw HTML, strict CSP | 2 |
| 13 | Upload validation | Yes (menu images, logos) | Size/type allow-list, content sniffing, re-encode, tenant-scoped private storage, signed URLs | 4 |
| 14 | Webhook verification | Only if an external provider is integrated (Q14) | Signature + timestamp + event-ID replay store | 6 (if applicable) |
| 15 | Rate limiting | Yes | Per-IP and per-account on auth; per-membership on writes; per-IP on any public endpoint | 2 |
| 16 | Tight CORS | Yes | Same-origin deployment preferred (no CORS needed); otherwise explicit origin allow-list | 2 |
| 17 | Production debug disabled | Yes | Settings refuse to start with debug in production env; CI check | 2 |
| 18 | Dependency patching | Yes | Lockfiles, automated update PRs, `pip-audit`/`npm audit` in CI | 2 |
| 19 | Claude-assisted security scanning | Yes | `security-engineer` review gate on every L2+ change; periodic full-repo `review-security` sweep | from 2 |

## Additional risks and their handling

| Risk | Handling |
|------|----------|
| CSRF | Cookie sessions → CSRF token on unsafe methods; `SameSite=Lax` minimum |
| IDOR / BOLA | Tenant-scoped lookups + object-level authz + cross-tenant tests |
| Session fixation | Rotate session ID on login and privilege change |
| Privilege escalation | Escalation guards in `authorization.md`, tested |
| Mass assignment | Allow-listed writable fields per endpoint |
| Unsafe deserialization | JSON only; no pickle/YAML full loader on input; job payloads JSON |
| SSRF | No user-supplied outbound URLs in v1; if added, host allow-list |
| Malicious uploads | Control 13 |
| Sensitive error disclosure | Standard error envelope; debug off; tested |
| Insecure cookies | `HttpOnly`, `Secure`, `SameSite`, host-only, `__Host-` prefix where possible |
| Weak password reset | Single-use, short-lived, hashed tokens; uniform responses; invalidate sessions on reset |
| Enumeration | Uniform responses/timing on login, signup, reset; rate limits |
| Race conditions | Named concurrency strategy per contended operation (`database-design`), tested |
| Replay | Idempotency keys on creates; webhook event-ID store |
| Database leakage | RLS, least-privilege roles, encrypted backups, no prod dumps in dev |
| Insecure logging | Redaction filter, no bodies of auth endpoints, audit separate from logs |
| Dependency vulnerabilities | Control 18 |

## Platform threat model

**Status:** v2 (change 0002, Track C2, 2026-09-30). Re-validated against the *Accepted* ADR-0003, ADR-0005 and ADR-0006 with their amendments, and against owner decisions C6.11–C6.14. v1 (Track C) was written against the Proposed ADRs. Re-run when an ADR is superseded, or when Q11 or Q14 are answered. Q9, Q71 and the Track C2 questions (Q72–Q75, Q78, Q80, Q83) were answered on 2026-09-30 (C6.15–C6.23); the control text below was synced to those decisions in change 0002 Track E without changing any control's strength. A security-engineer re-run against C6.15–C6.23 is a follow-up. `TM-nn` = threat, `NT-nn` = required negative test (input to the Phase 2 QA plan). Verdict: **PROCEED WITH CONTROLS**.

### Assets (priority order)
1. Tenant isolation itself (C1): any cross-tenant read or write is a critical incident.
2. Credentials, session IDs, device credentials and pairing codes, temporary (manager-set) passwords, PINs, and reset / verification / invite tokens.
3. Authorization state: memberships, roles, grants. Whoever controls it controls everything else.
4. Money state: orders, bills, payments, discounts, refunds.
5. Audit trail integrity (C5).
6. Personal data: staff identity and contact data, reservation customers.
7. Availability during service hours (order taking, kitchen channel).
8. Platform secrets: DB owner/migration credentials, framework secret key, email/storage provider keys.

### Actors
| Actor | Starting position | Typical goal |
|-------|-------------------|--------------|
| A1 Anonymous internet | none | account takeover, enumeration, email abuse, DoS |
| A2 Customer at a table (only if Q11 = yes) | holds a table QR | free/fake orders, other tables' orders |
| A3 Staff, same tenant, fewer permissions | active membership | discounts, refunds, voids, self-grant, reports |
| A4 Member of another tenant | valid session elsewhere | read/write tenant B via IDs, URL hint, channels |
| A5 Former / suspended staff | stale session or known password | continued access |
| A6 Owner | full tenant authority | repudiation; reaching beyond own tenant |
| A7 Platform operator | platform role | over-broad or unaudited tenant data access |
| A8 Compromised dependency, CI or worker | code execution | secrets, RLS bypass, exfiltration |
| A9 Whoever holds a shared device (Q7) | a paired kitchen/POS device session | act as the device or as the last switched-in person; guess colleagues' PINs |
| A10 Manager with `staff.manage` (C6.11) | sets and resets staff passwords | log in as a staff member; take over an identity that also belongs to another restaurant |

### Trust boundaries
- **B1 Browser to API.** Everything from the client is untrusted, including tenant hints, totals, and IDs.
- **B2 API to PostgreSQL.** The DB treats the app role as untrusted, so RLS still holds when app code is wrong.
- **B3 API to queue to worker.** A job payload is data, not authority. The worker re-establishes tenant context and re-reads state.
- **B4 Tenant plane to platform plane** (operator console, migrations, cross-tenant jobs). Separate credentials, a separate module, and audit.
- **B5 Platform to external services** (email, object storage; later payments).
- **B6 Identity plane to tenant plane.** Pre-tenant actions (login, restaurant switcher, invite acceptance) must read one user's memberships across tenants before any tenant context exists.

### Entry points
E1 auth endpoints (login, logout, password change, reset request/confirm, first-login forced change) · E2 email verification link · E3 owner invite create/lookup/accept (C6.6; staff are never invited, C6.11, and an existing user cannot be added as staff, C6.20) · E4 restaurant switcher and the tenant UUID in the URL path · E5 tenant API (all modules) · E6 uploads and file serving · E7 realtime kitchen/order channel · E8 background jobs and outbox · E9 platform operator console · E10 customer QR surface (only if Q11 = yes) · E11 migrations and deploy pipeline · E12 staff account creation and admin password reset (C6.11) · E13 device pairing and revocation (C6.14) · E14 PIN switch on a shared POS device (C6.13; not in v1, C6.17) · E15 PWA service-worker and client caches on shared devices.

### Threats and controls
L/I = likelihood / impact (H, M, L; C = critical impact).

| ID | Entry | Threat | L/I | Control | Negative test |
|----|-------|--------|-----|---------|---------------|
| TM-01 | E1 | Credential stuffing / brute force (S, API4) | H/H | Per-IP and per-account throttling, breached-password check, generic errors, MFA for owners (Q8) | NT-01 the Nth failed login is throttled; no success after the lockout threshold |
| TM-02 | E1-E3 | Account enumeration through signup/reset/invite responses or timing (I) | H/M | Identical body, status and timing; emails sent from a job | NT-02 known vs unknown email give identical responses |
| TM-03 | E1 | Login CSRF and session fixation (S) | M/M | CSRF enforced on *anonymous* POSTs too (DRF session auth skips CSRF for anonymous users); rotate session ID on login, restaurant switch, password or MFA change, and PIN switch-in/out (ADR-0006 C6-3, C6-8) | NT-03 login without CSRF token → 403; session ID differs before and after login |
| TM-04 | E1 | Session theft through XSS or a JS-readable token (I) | M/H | `__Host-` HttpOnly Secure SameSite cookie; strict CSP; no raw HTML; no token in any body | NT-04 cookie attributes asserted; no response body contains the session ID |
| TM-05 | E1,E5,E12 | Stale session after password reset (self or admin), membership removal or tenant suspension (S/E, A5) | H/H | Session store indexed by user (C6-4); delete all of a user's sessions on password change/reset (including admin reset, SP-06) or email change; check membership and tenant status on every request; timeouts 12 h idle / 30 d absolute for personal sessions (C6.12) | NT-05 old session → 401 after self or admin reset; removed member → 404 on the next request; session idle > 12 h or age > 30 d → 401 |
| TM-06 | E2 | Verify/reset token forgery, reuse, or leak through Referer/logs (S) | M/H | 256-bit random, stored hashed, single-use, short TTL, bound to user + purpose + email; the link opens a page that POSTs; `Referrer-Policy: no-referrer`; tokens redacted in logs | NT-06 reused, expired, wrong-purpose and wrong-user tokens are rejected |
| TM-07 | E3 | Invite accepted by the wrong account, replayed, or granting roles above the inviter; invite spam (S/E) | M/H | Invite bound to an email that the accepting user has verified; single-use hashed token; roles checked against the inviter's grants at create *and* accept; per-tenant rate limit; lookup and accept are POSTs with the token in the body; lookup only through the reviewed C3-1c function (TM-41) | NT-07 each of these cases is denied |
| TM-08 | E4 | Path tenant for a restaurant the user is not a member of; malformed or non-canonical UUID (I, API1) | H/C | Tenant only from the `/r/{tenant_id}/` path segment, parsed to a UUID and validated against an active membership inside the tenant transaction, else 404 (same response for malformed, unknown and non-member); never from body, query or header; the parsed canonical value, never the raw path string, is used for context, cache keys and channel names; the UUID is not treated as a secret (`Referrer-Policy: strict-origin-when-cross-origin` or stricter) | NT-08 non-member, unknown, malformed and upper-case variants of a UUID all give the identical 404 |
| TM-09 | E4 | Multi-tab confusion: tab 1 is on A, the user switches to B in tab 2, and tab 1's write lands in B (T) | H/H | Removed by construction (ADR-0006 C6-2): every request names its tenant in the path; the session default only drives landing redirects. For tenant-bound credentials (device sessions) a path tenant ≠ bound tenant returns 409 `tenant_mismatch` before any DB lookup, writes nothing and logs a security event (TM-43) | NT-09 tab A write after a switch in tab B lands in A; device bound to A calling any other well-formed UUID path → 409, identical for existing and non-existent tenants |
| TM-10 | E5 | BOLA/IDOR using the other tenant's IDs, including related IDs in bodies (I/T, API1) | H/C | Scoped repository, RLS, composite FKs; 404 | NT-10 two-tenant matrix on every endpoint |
| TM-11 | E5 | Missing function-level authorization (E, API5) | M/H | `require(code)`, default deny, route scan | NT-11 the route scan fails on an undeclared handler |
| TM-12 | E5 | Role self-grant, escalation, removing the last owner (E) | M/C | Escalation guards (`authorization.md`) | NT-12 |
| TM-13 | E5 | Mass assignment of `tenant_id`, status, price, version or membership (T, API3) | M/H | Allow-listed fields; unknown fields rejected; `tenant_id` not updatable by the app role | NT-13 |
| TM-14 | E5 | Price/total/discount tampering; skipping state-machine steps (T) | M/H | Server recomputes; commands only; money-affecting permissions kept separate | NT-14 |
| TM-15 | E5 | Replayed or double-submitted creates and payments; races on contended rows (T) | H/H | Idempotency keys scoped to (tenant, membership, key); row locks or `version` | NT-15 a concurrent duplicate has exactly one effect |
| TM-16 | E5 | Unbounded lists or reports during service (D, API4) | M/M | Page caps, bounded ranges, `statement_timeout` on the app role, report rate limits | NT-16 |
| TM-17 | E5 | Verbose errors; unique-violation or FK errors revealing another tenant's data exists (I) | M/M | Error envelope; every unique constraint leads with `tenant_id`; constraint names never returned | NT-17 same natural key in A and B → both succeed |
| TM-18 | E5 | Repudiation of money or permission actions; audit tampering (R) | M/H | Same-transaction audit; app role has INSERT/SELECT only on audit tables; actor is the membership (R7) | NT-18 the app role's UPDATE/DELETE on audit fails |
| TM-19 | E6 | Malicious upload (polyglot, SVG script, oversize, path traversal, cross-tenant key) (T/I) | M/H | Control 13; no SVG in v1; server-generated key `tenants/<id>/<uuid>`; served from a separate origin or via short-lived signed URLs with `nosniff` | NT-19 |
| TM-20 | E7 | Subscribing to another tenant's channel (I) | M/C | Server derives the channel from the resolved tenant; the client never names it | NT-20 |
| TM-21 | E7 | Authorization left stale on a long-lived connection (E) | H/M | Maximum stream lifetime (≤ 60 s, then reconnect and re-check); membership removal closes streams | NT-21 revoked member receives no events after the lifetime expires |
| TM-22 | E7 | Cross-site WebSocket hijacking (S) | M/H | Origin allow-list on the handshake; prefer same-origin SSE | NT-22 foreign Origin → rejected |
| TM-23 | E7 | Open streams exhaust connections or the DB pool (D) | H/H | Streams never hold a DB transaction; one short transaction per poll; per-membership stream cap | load test (Phase 5) |
| TM-24 | E8 | Job runs without tenant context, or with a forged or stale tenant; anyone with broker access enqueues jobs for any tenant (I/T) | M/C | Payload carries IDs and `tenant_id` only; one transaction per job with the tenant context set; re-read under RLS; fail closed; job types allow-listed and each job's effect re-derived from tenant state (a forged job can only do what that job type would do anyway); broker requires auth and TLS and is not reachable from outside the private network | NT-24 job for A leaves B untouched; job without context reads 0 rows; unknown job type rejected |
| TM-25 | E8 | `on_commit` or post-response code queries outside the tenant transaction (I) | M/M | `on_commit` only enqueues; review rule | NT-25 |
| TM-26 | E9 | Operator reads or changes tenant data without justification (I/E, A7) | M/C | Separate host and cookie; mandatory MFA; break-glass with a reason, time-boxed, audited into the tenant's audit log; operators never use tenant endpoints (Q5) | NT-26 |
| TM-27 | E10 | QR token forged, replayed or never expiring; order spam; seeing other tables' orders (S/T/D) | H/M | Only if Q11 = yes, under its own threat model: signed token with version and expiry, not accepted from the query string after the first scan, rate limits, customer sees only its own orders, staff confirm orders | deferred |
| TM-28 | E11 | New table without RLS; app role is owner or superuser, or has `BYPASSRLS`; views or definer functions bypass RLS; extra roles gain more than their stated grants (E, R1) | M/C | CI catalog check (tenancy.md): every tenant table has RLS enabled and forced plus a policy; app role is not owner, not superuser, no `BYPASSRLS`, not a member (directly or transitively) of the owner, migrator, scheduler or definer-owner role; views use `security_invoker`; the `SECURITY DEFINER` allow-list is pinned by function body hash; `rms_scheduler` and the definer owner hold exactly their listed grants; every role-targeted policy is on an allow-list | NT-28 |
| TM-29 | E11 | Owner/migration credentials reachable at runtime; secrets in logs (I, A8) | M/C | Runtime environment holds only app-role credentials; migrations run as a separate job; secret scan and redaction tests | NT-29 |
| TM-30 | B5 | Email links pointing to an attacker's host (Host header); tenant-controlled text used for phishing (T/S) | M/M | Links built from a configured base URL, never from `Host`; strict allowed hosts; tenant names escaped and length-limited | NT-30 |
| TM-31 | all | SSRF, unsafe deserialization, webhook forgery | L/- | Not applicable in v1: no user-supplied URLs, JSON only, no provider integration (Q14); revisit with Q14 | - |
| TM-32 | E12 | A manager who sets or resets a staff password knows it, can log in as that person, and weakens "who did it" (S/R, A10) | H/H | SP-01..SP-06, SP-08 | NT-32 a session opened with a temporary password gets 403 `password_change_required` on every endpoint except change-password, logout and `GET /me`; reusing the temporary password as the new one is rejected; an unused temporary password stops working after its expiry |
| TM-33 | E12 | A manager in A resets the password of an identity that is also a member or owner in B, then logs in as that user in B (cross-tenant account takeover) (E/S, A10) | M/C | SP-07, SP-08 | NT-33 manager of A resetting a user who has a membership in B → refused, password and sessions unchanged; a non-owner resetting an owner → refused; resetting oneself through the admin path → refused |
| TM-34 | E12 | Pre-account hijacking: a manager creates a staff account with someone else's email and keeps the password; that person later verifies the email or is invited as an owner and inherits a credential the manager knows (S) | M/H | SP-09 | NT-34 no reset link or account email is sent to a staff email (C6.21); owner invite to an identity whose email is unverified is not accepted; the clause "verification by the email holder invalidates the previous password and ends all sessions" is not applicable in v1, because staff email verification does not exist (C6.21), and applies if it is ever introduced |
| TM-35 | E12 | Identifier enumeration or squatting through staff creation ("email/username already taken"); adopting an existing identity into a new restaurant (I/E) | M/M | SP-07, SP-10; creation with an existing identifier is refused (C6.20) | NT-35 creating staff with an identifier that exists elsewhere reveals no other restaurant, sets no password and creates no active membership; creation is rate-limited per membership and per tenant |
| TM-36 | E12 | Temporary password leaks through logs, audit payloads, error reports, HTTP caches or email (I) | M/H | SP-04 | NT-36 the redaction test covers create/reset request and response bodies; the create/reset response carries `Cache-Control: no-store`; the audit event contains no password field |
| TM-37 | E5, E13 | A device session acts beyond its purpose: too-broad device-eligible set, or a POS device takes orders or payments without an identified person (E/R, A9) | M/H | DV-01, DV-02, PN-10 | NT-37 a device granted a never-eligible code is rejected at pairing; a POS device with nobody switched in gets 403 `individual_required` on order and payment commands; a kitchen device's actions are audited with the device as actor |
| TM-38 | E14 | PIN brute force, spraying one PIN across all names, shoulder surfing, or offline cracking after a DB/backup leak (S, A9) | H/H | PN-03..PN-06 | NT-38 the 6th consecutive wrong PIN for a membership is delayed and the 11th disables it; failures across many names on one device trigger a device cool-down; trivial PINs rejected; the PIN hash cannot be verified without the pepper |
| TM-39 | E14 | PIN used as a primary credential (outside a paired device, or on another restaurant's device), or switching in lifts the device to the member's full permissions (E) | M/C | PN-01, PN-02, PN-11 | NT-39 no PIN endpoint exists outside the device plane; a PIN on a device of B for a member of A fails; a switched-in manager on a POS device still gets 403 on `roles.manage` and on identity-plane endpoints |
| TM-40 | B6 | The user-scoped membership policy (C3-1a) widens a tenant-plane query or allows writes (I/T) | L/C | Policy is `FOR SELECT` only, guarded by `NULLIF(app.tenant_id) IS NULL`; `app.user_id` set only by the identity entry point via `set_config(..., true)` from the authenticated session | NT-40 in a tenant transaction for A, a user with memberships in A and B sees only A's rows; in the identity plane, UPDATE/DELETE on memberships affects 0 rows; without `app.user_id` the identity plane sees 0 rows |
| TM-41 | E3 | Invite-lookup definer function (C3-1c) misused: callable by `PUBLIC`, `search_path` hijack, more than one row returned, body changed without review, or its owner role reachable with `SET ROLE` (E/I) | L/C | Conditions in change 0002 Track C2 point 2: `EXECUTE` revoked from `PUBLIC` and granted only to `rms_app`; pinned `search_path` ending in `pg_temp`, all names schema-qualified; no dynamic SQL; fixed-length hash input; unique index on the hash; body hash pinned in the CI allow-list; the owner role has no members at runtime; prefer role-targeted SELECT policies over `BYPASSRLS` | NT-41 a role other than `rms_app` cannot execute it; a wrong or short hash returns 0 rows; the catalog check fails if the body changes |
| TM-42 | E8 | `rms_scheduler` credential over-granted or present in API/worker environments, turning into a tenant list or a tenant-data reader (I) | L/M | Grants exactly SELECT on registry `id`, `status`; no tenant tables, no DML, no role memberships, no `BYPASSRLS`; timeouts set; credential only in the scheduler environment | NT-42 catalog check asserts the scheduler's grants; runtime env check asserts API and worker hold no scheduler credential |
| TM-43 | E13 | Device paired by someone without `devices.manage`; pairing code guessed, intercepted or replayed; a device cookie copied and used elsewhere (S/E) | M/H | DV-02..DV-05 | NT-43 issuing a code without `devices.manage` → 403; a used, expired or other-tenant code → rejected, with a uniform response and rate limits; the pairer lost `devices.manage` before redemption → rejected; a revoked device → 401 on its next request, open stream closed; a device bound to A calling B → 409 and a security event |
| TM-44 | E13 | Device sessions have no idle or absolute timeout (C6.12), so a stolen or copied device credential works forever (S) | M/H | DV-04 rotation; device list with last-seen; per-device revocation | NT-44 after rotation the previous credential fails once the grace period ends; the device itself keeps working |
| TM-45 | E15 | PWA service-worker or client caches show the previous user's data on a shared device, or after logout, PIN switch-out or device revoke (I) | M/M | The service worker never caches `/api/` responses; authenticated API responses send `Cache-Control: no-store`; client state and caches are cleared on logout, switch-out and revoke | NT-45 after logout or switch-out, no cached API data is visible offline; response headers asserted |
| TM-46 | E1 | Progressive login delay used to keep a colleague out during service (D) | M/M | Delay keyed per (account, source) with a capped per-account component; no permanent lockout (C6.12); generic errors; security events for bursts | NT-46 failures from source X do not delay the same account's login from source Y beyond the cap |

### Controls: manager-set staff passwords (C6.11)
The owner chose manager-set initial passwords instead of email invites for staff. These controls make that acceptable. Items that needed owner approval (change 0002, Track C2 questions) are now marked with the decision that settled them (C6.15, C6.16, C6.20, C6.21, C6.23).
- **SP-01 Forced change at first login** *(decided, C6.15)*. An admin-set or admin-reset password is marked temporary. A login with it opens a restricted session: only change-password, logout and `GET /api/v1/me` work. Every other endpoint returns 403 `password_change_required`. The server enforces this at the entry points, not the client.
- **SP-02 Temporary password expiry** *(decided, C6.15)*. An unused temporary password stops working after 72 h. A manager must then reset it again.
- **SP-03 New password.** It must differ from the temporary one and meet C6.12 (minimum 10 characters, breached-password check). Setting it rotates the session and deletes all other sessions of the user.
- **SP-04 Never view.** Passwords are stored only as Argon2id hashes. No endpoint, screen, audit event, log or export shows a password after it is set. The system generates the temporary password *(decided, C6.15)*; it appears once, in the create/reset response, with `Cache-Control: no-store`. It is never emailed, never put in a URL, and is redacted from logs and error reports.
- **SP-05 Audit and notice.** Account creation and admin reset are audit events: actor membership, target membership, tenant, time, outcome, no password value. They are also security events. At next login the staff member sees "Your password was reset by <manager> on <time>" (notice at sign-in, C6.23).
- **SP-06 Reset ends sessions.** Admin reset deletes all of the target user's personal sessions and clears their PIN (PN-08, once PIN switch exists; C6.17).
- **SP-07 Tenant-managed identities only** *(decided, C6.16, C6.20)*. A manager may set or reset the password only of an identity that their restaurant created, that has no membership in any other restaurant, and that is not an owner anywhere. For any other identity the reset is refused, and the manager can suspend the membership instead (effective on the next request). Staff creation never adopts an existing identity: an email or username that already belongs to a user is refused, no password is set, and the message never names another restaurant (C6.20). There is no path that adds an existing user as staff. An existing user joins another restaurant only as an owner, through an invitation they accept (C6.6, C3-1c).
- **SP-08 Authority guards.** Create and reset require `staff.manage` in the path tenant. The actor is never the target (own password goes through self-service change, which requires the current password). A non-owner never resets an owner. The actor must hold every permission the target membership holds. This extends "grant only what you hold" to the power to impersonate. Decided *(C6.16)*: owners are never reset by managers; they use the email reset link, or platform-assisted recovery (Q34, open). Security's recommendation that another owner holding `owners.manage` also never admin-resets an owner is not explicitly stated in C6.16 and remains open (change 0002, Track E).
- **SP-09 Unverified email grants nothing.** A manager-entered email is unverified. No reset link is sent to it. It cannot accept an invite or become an owner. When the holder of that email verifies it, the previous password is invalidated, all sessions end, and they set a new password. This defeats pre-account hijacking.
  - *v1 applicability (C6.21):* staff email is contact information only. "No reset link" and "no account email" hold for every staff email, because v1 has no staff email features. "Cannot accept an invite or become an owner" still applies. The verification clause is **not applicable in v1 (C6.21)**: no staff email verification exists; it applies if staff email verification is introduced later.
- **SP-10 Enumeration and abuse.** Staff creation is rate-limited per membership and per tenant, and audited. A conflict on an existing identifier reveals nothing about other restaurants or the account.
- **SP-11 Login policy (C6.12).** The breached-password check sends no password or full hash out of the system. Use an offline corpus or a k-anonymity range query; a third-party service here is a REVIEW/APPROVAL choice for the architect. Progressive delay as in TM-46. Staff have no email self-reset in v1 (C6.21); they rely on manager reset (SP-05..SP-08, C6.15, C6.16).

### Controls: PIN switch on a shared POS device (C6.13)
**Planned — not in v1** (C6.17: no counter/POS device profile in v1; PIN switch later, C6.4). These controls bind the PIN feature when it is built; PIN rules marked *(owner)* are open as Q81.
- **PN-01 Never a primary credential.** A PIN is accepted only on a paired, active POS device session of the path tenant. No identity-plane or personal-session PIN endpoint exists. A PIN alone never creates a session and never reaches another restaurant.
- **PN-02 Scope and permissions.** A PIN belongs to a membership (one restaurant), not to the user. While someone is switched in, effective permissions = the device's permission set ∩ the membership's current permissions, evaluated per request. A suspended or removed membership, or a revoked device, ends the switch on the next request.
- **PN-03 Pick, then PIN.** Staff choose their name tile, then enter the PIN. There is no PIN-only lookup and no uniqueness rule on PINs, since uniqueness would reveal colleagues' PINs.
- **PN-04 Length and quality** *(owner)*. At least 6 digits (4 is too weak given many staff per device and shoulder surfing). Reject trivial PINs: all digits the same, ascending or descending runs, and a common-PIN list.
- **PN-05 Storage.** Slow hash (Argon2id) with a per-PIN salt and a server-side pepper (a key in the secret manager, not in the DB). A DB or backup leak alone therefore does not allow cracking the 10^6 space.
- **PN-06 Throttling** *(owner, for disablement)*. Server-side counters. Per membership: a progressive delay from the 6th consecutive failure; the PIN is disabled after 10 until the staff member sets a new one from a password login. A lockout is acceptable here because the password remains the fallback. Per device: failures across many names trigger a device cool-down and alert holders of `devices.manage`.
- **PN-07 Set and reset.** Staff set their own PIN after re-entering their password. A manager can clear a PIN (audited) but never set or view it. PINs are never shown, logged or returned. PIN entry is a CSRF-protected POST with the PIN in the body. Every failure gets the same response.
- **PN-08 Lifecycle.** A password reset (self or admin) clears the PIN, and membership suspension disables it. Set, change, clear and disable are audit events.
- **PN-09 Server-side switch state.** The device session row holds the acting membership, the switch-in time and the last activity. The client never asserts who is acting. Switch-in and switch-out rotate the device session ID. Automatic switch-out happens after inactivity (suggested 90 s, *owner*) and on an explicit lock.
- **PN-10 Attribution.** The audit actor is the membership plus the device. On a POS device with nobody switched in, the commands C6.13 requires to be individually attributed (order create/update/cancel/discount, take payment) return 403 `individual_required`. Idempotency keys are scoped to (tenant, device, acting membership, key). The same key from a different acting membership returns 409.
- **PN-11 No personal reach.** Switching in gives no access to profile, password change, other restaurants or identity-plane endpoints.

### Controls: device sessions (C6.12–C6.14)
- **DV-01 Eligibility** (approved by the product owner, C6.25, 2026-09-30). **D** (device-attributed): `kitchen.view`, `kitchen.update`, `menu.view`, `menu.availability` only. `orders.view` and `tables.view` are not device-eligible in v1; `orders.view` is reserved for the future PIN counter profile. **P** (only with someone switched in, PN-10; unused in v1, C6.17): `orders.create`, `orders.update`, `billing.view`, `billing.take_payment`. Everything else is never eligible, including all staff, roles, owners, settings, devices, audit, reports, history, refund, cancel, discount and price codes. The device profile is fixed at pairing. The server re-checks eligibility on every request, so a later catalog change cannot silently widen existing devices.
- **DV-02 Pairing** (design adopted in `authorization.md` and `domain-model.md`). A member with `devices.manage` in the path tenant starts pairing in their personal session and gets a single-use pairing code: random, at most 10 minutes' lifetime, stored hashed, bound to the tenant and to the chosen device kind and profile. The code is entered on the tablet by a CSRF-protected POST, is rate-limited per source, and is consumed on first use. No personal credential is typed on the shared device. The profile is capped by the eligibility list and by the pairer's own permissions, re-checked when the code is redeemed. Issuing and redeeming are audited. Rejected alternative: converting a personal session on the tablet, because it puts a manager's password (and possibly a saved browser password) on a shared device.
- **DV-03 Revocation.** Per device, effective on the next request. Open streams close. The device list shows last-seen.
- **DV-04 Rotation** (answers the REVIEW in `authorization.md`: yes, rotate). C6.12 gives shared devices no idle or absolute timeout. The device credential therefore rotates server-side (suggested every 24 h, with a short grace for the old value): a copied cookie stops working while the device keeps running. Devices not seen for a set number of days are flagged to managers. Automatic revocation would be a new business rule *(owner, Q82 open)*.
- **DV-05 Tenant binding.** A path tenant ≠ the bound tenant returns 409 `tenant_mismatch` before any DB lookup. Nothing is written, and a security event is logged (TM-09).

### Required DB-layer specifics (from the ADR-0003 review, change 0002 Track C)
- Set tenant context with `SELECT set_config('app.tenant_id', %s, true)` and a bound, UUID-validated parameter. Never build `SET LOCAL` as a string; never set it at session level (`is_local = false`).
- Policy expression: `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid`. Once a session has set the custom setting, it reverts to `''` rather than NULL.
- Enforce `tenant_id` immutability (column privilege or trigger).
- App role: `statement_timeout` and `idle_in_transaction_session_timeout` set.
- Test and CI databases connect as the app role. A superuser bypasses RLS even with `FORCE`.
- Pre-tenant membership and invite lookups (B6) use only the sanctioned identity-scoped path: C3-1a user-scoped SELECT policy and the C3-1c invite-lookup function (accepted 2026-09-30). Conditions: TM-40, TM-41.

### Residual risks
- Business-logic flaws inside one tenant (A3) are limited only by the catalog, the guards and tests.
- An owner abusing their own tenant cannot be prevented; audit gives accountability.
- Shared-device attribution (R7): kitchen displays are device-attributed by owner decision (C6.13). v1 keeps order and payment codes off devices: there is no counter/POS profile (C6.17, TM-37). POS attribution later depends on PIN switch (PN controls).
- A manager who sets or resets a staff password can act as that staff member until the staff member changes it (R19, consequence of C6.11). Forced change, 72 h expiry, audit and notification limit but do not remove this. Accepted by the product owner (C6.23).
- A 6-digit PIN is a weak secret. It is safe only as a second factor on top of a paired device (R21). Not in v1 (C6.17).
- Shared device sessions have no idle or absolute timeout (C6.12). A copied device cookie lives until revoked unless the credential rotates (TM-44, R23).
- Whoever holds the DB owner credentials or backups can read all tenants. Process and audit mitigate this, not RLS.
- Taking over a user's email means taking over their RMS account unless MFA is on (Q8).
- Noisy-neighbour load in a shared database (ADR-0003 "Revisit when").

## Security gates
Security analysis before implementation and security review after (`docs/process/workflow.md`). The `security-engineer` can `BLOCK`.
