# 0002 — Phase 1: decisions and discovery

- **Status:** Done (2026-09-30)
- **Risk level:** L2 — documents only, but outputs (ADR acceptance, permission catalog, business rules) are `APPROVAL`-class inputs to later phases
- **Requested by / date:** product owner ("carry on"), 2026-09-30
- **Current gate:** 2 (Requirements) — parallel discovery tracks running

## 1. Request
Execute Phase 1 of `docs/product/roadmap.md`: answer blocking open questions, settle ADR-0003..0006, produce requirement briefs, domain model, core UX flows, platform threat model and permission catalog v1. No production code.

## 2. Requirements
Tracks and outputs:
- A. `requirements-analyst` → `docs/product/briefs/` per area (identity & access, restaurant setup & staff, menu, tables, orders & kitchen), each with acceptance criteria and open questions. Legacy `../rms` mined for edge cases.
  - _Track A summary (requirements-analyst, 2026-09-30):_ five Draft briefs in `docs/product/briefs/`: `01-identity-access.md` (IA-1..21), `02-restaurant-setup-staff.md` (RS-1..19), `03-menu.md` (MN-1..16), `04-tables.md` (TB-1..12), `05-orders-kitchen.md` (OK-1..20). Each has goal, actors/context, happy paths, testable criteria, edge/failure cases, must-have vs optional, legacy evidence labelled "unconfirmed", and references Q1–Q25/UX-n by number. Briefs are written against the answers listed below (Q1, Q2, Q4–Q7, Q19, Q21). New questions Q26–Q70 added to `requirements.md` open questions (nothing added to Confirmed). Blocking: Phase 2 — Q26, Q27, Q29, Q30, Q33; Phase 3 — Q31, Q36–Q38, Q40, Q42; Phase 4 — Q45, Q48, Q49, Q54, Q55; Phase 5 — Q44, Q50, Q59–Q63, Q69. Duplicates linked: Q32 = UX-1, Q61 = UX-2, UX-3 folded into Q59. For Track D: order lifecycle depends on Q59–Q62, table states on Q54, membership/invite on Q26–Q28.
- B. `ux-designer` → `docs/product/ux-flows.md`: navigation model and core flows (sign-in, switch restaurant, take order, kitchen ticket, staff invite).
  - _Track B summary (ux-designer, 2026-09-30):_ `docs/product/ux-flows.md` (Proposed). Permission-driven bottom tabs (≤ 4 + More, last-used home tab), restaurant name/switcher always in top bar, kitchen full-screen mode as a device session (Q7 default). Flows F1–F6 with tap counts and all states: sign in 1–2 taps, switch 2, invite 5–6, table order 3 (plain items), kitchen Start/Ready 1 each with undo, served 2, close 4 with confirm. Built on defaults of Q6, Q7, Q8, Q9, Q12, Q13, Q14, Q19. New questions UX-1..UX-6 (UX-2 void-after-send rules blocks Phase 5; UX-5 kitchen device sign-in permission blocks Phase 2 with Q7). REVIEW items: direct entry to last-used restaurant; confirm on high-risk role invites.
  - _Track B update (ux-designer, 2026-09-30):_ per C6.11/C6.13/C6.14, F3 is now "Add staff member" (system-generated temporary password on a show-once hand-over screen with no copy/share, forced change at first sign-in, audited reset; Depends on Q71 default, AQ1, AQ2; 6–7 taps), owners keep the email invitation (C6.6), new F7 "Pair a shared device" (DV-02 code, 4 taps on phone + 2 on tablet, revoke 5 with confirm), F8 PIN switch-in noted as a later flow (AQ4); staff "Invited" state removed. REVIEW: no copy/share of the temporary password.
- C. `security-engineer` → platform threat model section in `docs/architecture/security.md`.
- D. `architect` (after A) → domain model moved toward `Accepted`, lifecycles drafted.
- E. Human → answers to blocking questions; ADR decisions.

Open questions (answers recorded here and in `requirements.md`):
Answered by the product owner, 2026-09-30:
- Q1 — Nepal first (NPR, Asia/Kathmandu); multi-currency-ready design.
- Q4 — One tenant = one restaurant location; multi-branch groups later, as a layer above.
- Q23 / ADR-0004 — Django + DRF + PostgreSQL; React + TypeScript + Vite as an installable PWA. ADR-0004 → Accepted.
- Q6 / Q7 — Personal login (email/username + password) on personal devices; shared kitchen/counter tablets use a limited device session; PIN quick-switch later.
- Q19 — Tolerate brief network loss (pending state, idempotent retry, kitchen reconnect + catch-up); no full offline mode in v1.
- Q21 — English only in v1, i18n-ready (no hard-coded user-facing strings).
- Q2 / Q5 — Platform operator creates tenant + owner invite; operator console has no tenant data access except audited break-glass.
- Q24 / Q25 — Legacy `../rms` was local only; nothing to migrate; its committed secrets were never used outside dev (still never reused).

Second round, 2026-09-30:
- ADR-0003 — Accepted with changes C3-1..C3-10; C3-1 resolved by options (a)+(c): user-scoped RLS policy on memberships via `app.user_id` exposing only restaurant name/status, invite lookup by token hash through one reviewed definer function.
- ADR-0006 — Accepted with changes C6-1..C6-8: single host, restaurant in URL path, tenant resolved + validated per request (409 on mismatch), `__Host-` cookies, custom session store supporting logout-all, login CSRF fix, Origin check on realtime handshakes.
- ADR-0005 — Accepted.
- Q8 — Optional TOTP MFA for owners; mandatory for platform operators.
- Q20 — Orders, payments and audit retained 7 years; staff personal data minimized after membership removal.

Fourth round, 2026-09-30 (product owner, direct answers):
- Q71 — Temporary staff passwords are system-generated and shown once; forced change at first login; unused temporary password expires after 72 h; managers can reset but never view; each reset is audited and ends the person's sessions. (→ C6.15)
- Reset scope (security C2 Q2, R20) — A manager may reset only accounts their restaurant created that have no membership elsewhere and are not an owner anywhere. Owners are never reset by managers; they use the email reset link. (→ C6.16)
- POS tablet (AQ4 / C2 Q3) — No counter/POS device profile in v1; only the kitchen display device. Staff take orders and payments on their own logged-in devices. PIN switch comes later. (→ C6.17)
- Username scope (AQ2 / C2 Q5) — Usernames are unique platform-wide. (→ C6.18)

Fifth round, 2026-09-30 (product owner, direct answers):
- Q9 — Catalog v1 + default roles approved as proposed. (→ C6.19)
- Q72 — Existing users cannot be added as staff; use a different identifier. (→ C6.20) Note: the architecture still supports multi-restaurant users (C2.4); only the add-staff path is restricted.
- Q74 — No staff email features in v1; all staff resets via manager. (→ C6.21)
- Q78 — Audit payload defaults adopted. (→ C6.22)
- Q83 — R19 accepted by owner. (→ C6.23)

Sixth round, 2026-09-30 (product owner, direct answers):
- Staff sign in with username only (→ C6.24).
- Kitchen display device profile and device-eligibility list approved; Q48 sold-out marking answered (→ C6.25). Resolves the DV-01 vs authorization.md mismatch: `orders.view` is PIN-only.
- Domain model sections marked "Ready for acceptance" accepted.
- Phase 1 closed; Phase 2 opened.

Deferred to Phase 3 (not blocking Phase 2): whether owners may reset other owners (C6.16 gap); re-hiring a removed person vs C6.20 (Q41); owner invitation to an email held as staff contact info.

Previously listed as still open and blocking Phase 2 (now resolved): UX-5 (which permission signs a kitchen device in/out).

## Track C — Security analysis (security-engineer, 2026-09-30)

Threat model: `docs/architecture/security.md` → "Platform threat model" (TM-01..31, NT-nn tests). Verdict: **PROCEED WITH CONTROLS**. New risks R11-R18 in `docs/risks.md`. ADR status is not changed here; accepting an ADR is the human's decision (E).

### ADR-0003 (shared schema + RLS): recommendation **accept with changes**
The strategy is sound and better than the legacy schema-per-tenant. As written, it has these gaps:

| # | Finding | Severity if left | Required change |
|---|---------|------------------|-----------------|
| C3-1 | **Pre-tenant reads conflict with RLS.** `tenancy.md` makes memberships (and presumably invites) tenant-owned, yet login, the restaurant switcher and invite acceptance must list one user's memberships across tenants *before* a tenant context exists. Under the policy those reads return 0 rows, which pushes implementers toward an unscoped bypass. | high | Define one sanctioned identity-scoped path. Options: (a) a second policy on `membership` (and a read-only tenant name/status view) using `app.user_id`; (b) a small reviewed `SECURITY DEFINER` function returning only (tenant_id, name, membership status) for the session user; (c) invite lookup by token hash through a definer function. Changes the tenant boundary → **APPROVAL**. |
| C3-2 | `SET LOCAL app.tenant_id = '<uuid>'` cannot take bind parameters, so it invites string-built SQL. | medium | Use `set_config('app.tenant_id', %s, true)` with a validated UUID parameter; forbid session-level setting; test that a pooled or persistent connection reused by the next request has no tenant set. |
| C3-3 | After a session has set a custom setting, it reverts to `''`, not NULL, and `''::uuid` raises. The result is intermittent 500s on reused connections, which creates pressure to "fix" the policy. | medium | Policy uses `NULLIF(current_setting('app.tenant_id', true), '')::uuid`. |
| C3-4 | "Every request runs in a transaction" is necessary but not enough. Queries in middleware, auth/session lookup, throttling, `on_commit` callbacks, streaming responses and post-response hooks run outside it. They fail closed, which is safe but pushes developers toward bypasses. | medium | One tenant-transaction entry point (middleware or handler decorator) that the scoped repository asserts is active; `on_commit` only enqueues; streaming uses one short transaction per poll. |
| C3-5 | Non-owner role is under-specified: role *membership* in the owner role, superuser, `BYPASSRLS`, views without `security_invoker`, `SECURITY DEFINER` functions and materialized views all bypass RLS silently. | high | CI catalog test (extends R1) asserting each of these conditions. |
| C3-6 | **Migrations role vs `FORCE`.** With `FORCE ROW LEVEL SECURITY` the owner is subject to RLS too, so data migrations see 0 rows unless they set context or the role has `BYPASSRLS`. The ADR does not say which, or how the Django `migrate` credentials stay out of the runtime. | medium | Migrations run as a separate job with a separate DB alias and credentials that are absent from API and worker environments. Data migrations iterate tenants from the registry and set context per tenant; `BYPASSRLS` only with a written reason. `ALTER DEFAULT PRIVILEGES` grants the app role DML only. |
| C3-7 | Test databases usually connect as a superuser, which bypasses RLS even with `FORCE`, so every RLS test would pass vacuously. | high | Test runner connects as the app role; a guard test asserts `current_user` is not superuser and has no `BYPASSRLS`. |
| C3-8 | Background jobs across tenants (nightly tasks) need to enumerate tenants. That is a platform-plane read and is not described. | medium | Scheduler reads the tenants registry (platform table), then enqueues one job per tenant; the worker sets context per job (TM-24). |
| C3-9 | `tenant_id` mutability and the unique-constraint oracle are not stated. | low | App role cannot UPDATE `tenant_id`; every unique constraint leads with `tenant_id`. Composite FK needs `UNIQUE (tenant_id, id)` on parents. |
| C3-10 | Pooler: transaction pooling (PgBouncer) is compatible with `set_config(..., true)`, but Django `CONN_MAX_AGE` persistent connections plus a session-level mistake would leak context across requests. | medium | Covered by C3-2 test; add `idle_in_transaction_session_timeout` and `statement_timeout` on the app role. |

Legacy evidence: `../rms/backend/apps/audit/streaming.py:29,45` keys the realtime channel by the connection's current schema (`rms:{schema}:events`). That is the "silent `search_path` leakage" class ADR-0003 cites. A shared-schema design must derive channel names from the resolved tenant, never from connection state (TM-20).

### ADR-0006 (server-side sessions): recommendation **accept with changes**
The right choice over legacy JWT-in-cookie. Gaps:

| # | Finding | Severity if left | Required change |
|---|---------|------------------|-----------------|
| C6-1 | **Cookie scoping and a restaurant in the URL.** If tenants get subdomains, host-only cookies force a re-login per restaurant. A parent-`Domain` cookie lets any subdomain read and overwrite it (cookie tossing, fixation), and sibling subdomains are "same-site", so SameSite gives no CSRF protection between them. | high | One host; restaurant in the **path** (`/r/<tenant>/…`); cookie `__Host-` prefixed (Secure, `Path=/`, no `Domain`). User-uploaded files are served from a different registrable domain or through signed object-storage URLs. |
| C6-2 | "The session stores the active membership ID" is a single mutable value shared by every tab. A switch in one tab silently retargets writes from another tab to a different restaurant (TM-09). Not a cross-tenant leak, since the user is a member of both, but a wrong-tenant write of money or orders. | high | Resolve tenant per request from the URL path and validate it against memberships; the session holds only a default. On mismatch with the client's expected tenant → 409, no write. |
| C6-3 | **Login CSRF.** DRF `SessionAuthentication` enforces CSRF only for authenticated users, so anonymous login/signup/reset POSTs are unprotected by default. | medium | Enforce CSRF on all unsafe methods, authenticated or not; strict `CSRF_TRUSTED_ORIGINS`; no GET with side effects (invite accept, verify confirm by POST). |
| C6-4 | "Invalidate all sessions of a user" is impossible with the default Django DB session backend: no user index, and data is opaque. | medium | Custom session model/backend with `user_id` and `created_at`/`last_seen_at` columns (for absolute and idle timeout). Session key stored hashed (a DB read otherwise yields live sessions). Serializer is JSON only, never pickle. |
| C6-5 | Session store choice left open (PostgreSQL or Redis). A Redis store shared with the Celery broker means broker compromise equals session hijack, and it adds an unauthenticated-by-default service. | low | Prefer PostgreSQL (platform-level table, no RLS, accessed only by the identity module). If Redis, use a dedicated instance or ACL user with TLS and auth. |
| C6-6 | Realtime channel: WebSocket handshakes are not covered by Django CSRF. | medium | If WebSocket, check `Origin` against an allow-list; prefer same-origin SSE; bounded stream lifetime (TM-21/22). |
| C6-7 | Shared devices (Q7) and the platform console are not addressed. A kitchen tablet with an owner's long-lived session is a standing escalation. | medium | Device sessions are a separate credential type with a fixed limited permission set, per-device revocation and no idle logout (separate decision once Q7 is answered). Operator console uses its own cookie name and host, mandatory MFA and a short absolute timeout (Q5). |
| C6-8 | Rotation triggers: "privilege change" can only rotate the acting user's own session. | low | Rotate on login, restaurant switch, password/MFA change. Other users' changes rely on per-request evaluation (already in ADR-0005). |

### Decisions and approvals
- Threat model content, control choices and test list: `REVIEW` (security-engineer, this track).
- C3-1 identity-scoped membership/invite path: **APPROVAL** (tenant boundary).
- C6-1 path-based tenant URLs on a single host: **APPROVAL** (auth/cookie architecture), to be decided with ADR-0006.
- C6-7 device sessions: **APPROVAL**, after Q7.

### Questions for the human (E)
1. (blocking Phase 2) Accept ADR-0003 with changes C3-1..C3-10? Which option for C3-1?
2. (blocking Phase 2) Accept ADR-0006 with changes C6-1..C6-8, including the single host with the restaurant in the path?
3. (blocking Phase 2) Q7: device sessions for kitchen/POS, yes or no? This decides whether C6-7 needs its own ADR.
4. (non-blocking) Q11: if customer QR ordering comes back into scope, it needs its own threat model before Phase 5. Legacy accepted non-expiring tokens from the query string (`../rms/backend/apps/order/viewsets.py:50-62`).

## Track D1 — ADR amendments (architect, 2026-09-30)
Recorded the product owner's second-round decisions. These are documents only; nothing is built.
- **ADRs.** 0003, 0005 and 0006 → `Accepted (product owner, 2026-09-30, change 0002)`. 0003 and 0006 gained an "Amendments at acceptance" section listing C3-1..C3-10 and C6-1..C6-8 (plus Q7 and Q8). Their Decision text points to the amendments, which win where they differ.
- **`tenancy.md`** → Accepted. Adds:
  - three planes (tenant / identity / platform);
  - tenant resolved from the path inside one tenant-transaction entry point;
  - `set_config(..., true)` with a bound UUID, and a `NULLIF` policy;
  - a SELECT-only user-scoped membership policy that applies only when no tenant is set, with restaurant name and status via column grants plus RLS;
  - one invite-lookup definer function, owned by a `NOLOGIN` role with a written `BYPASSRLS` reason;
  - DB roles: app, migrator, scheduler, and the definer owner;
  - a separate migration job and credentials;
  - the CI catalog check and tests run as the app role.
- **`authorization.md`** → model Accepted. Adds per-request membership from the path, membership lifecycle and retention (Q20), authentication and sessions (`__Host-` cookie, PostgreSQL store, hashed keys, CSRF on anonymous POSTs, rotation, MFA per Q8, operator console), and device sessions (Q7). The catalog is still a draft.
- **`overview.md`.** Decision table statuses updated, retention row added, diagram shows the scheduler, the migration job and the single host with path tenant.
- **`docs/conventions/api.md`.** URL layout proposal (REVIEW): identity plane `/api/v1/auth|me|invites/…`, tenant plane `/api/v1/r/{tenant_id}/…` using the tenant UUID, platform plane on the operator host. 404 for a non-member path, 409 `tenant_mismatch` for a tenant-bound credential used against another path, 403 `csrf_failed`.
- **`risks.md`.** R11, R13, R14, R16 and R17 marked "mitigation accepted as design", still Open until Phase 2.
- **Decisions.**
  - REVIEW: tenant UUID (not a slug) in the path; the separate `rms_scheduler` credential; the definer-owner role with `BYPASSRLS`; the list of codes that are never device-eligible.
  - REVIEW: the meaning of the 409 mismatch. With the tenant in the path, multi-tab confusion is removed by construction, so 409 applies to tenant-bound credentials.
  - APPROVAL (still open, not decided here): UX-5; the device permission set (with Q9).
- **Follow-ups for other owners.**
  - `.claude/rules/tenant-isolation.md` line 5 and the `api-design` skill step 3 still say "active membership". Updating them is a process change and needs approval.
  - `security.md` status line references the *Proposed* ADRs, so security-engineer should re-run the threat model against the accepted ones.
  - `domain-model.md`: the "Device session" term is still "Pending Q7" (Track D).
  - `data.md`: the retention mechanism.
  - `overview.md` line 7 says "pending Q23" (ADR-0004 is Accepted).
  - Q20 details go to `requirements.md`: which personal fields are minimized, when, and how an actor is displayed. So do the MFA recovery method and non-owner TOTP.

## Track D2 — Domain model, catalog v1, retention (architect, 2026-09-30)
Documents only. No code exists yet (`backend/` and `frontend/` absent), so the evidence is docs.

**Outputs.**
- `docs/architecture/domain-model.md`, per-section status:
  - Ready for acceptance: vocabulary; contexts and dependencies; Invitation; Membership; Device.
  - Proposed: Restaurant status (Q39, Q3); Menu availability (Q48, Q49); Table (Q54–Q56); Order (Q59–Q62, Q69); Line/ticket (Q59, Q61/UX-2, Q63, UX-3).
  - Each lifecycle has a transition table (command, permission, side effects, dependency) and invariants with an enforcement point (DB / Svc / Entry).
- `docs/architecture/authorization.md`:
  - membership states reconciled with C6.11;
  - device session valid until revoked (C6.12);
  - catalog v1 with device eligibility, role templates matrix and dependency table.
- `docs/architecture/data.md`: retention classes and minimization principles (C6.8).

**Impact.**
| Area | Effect | Evidence |
|---|---|---|
| access / identity | Membership has no `invited` state. Invitation becomes its own entity (owners only). Staff accounts are created directly | C6.6, C6.11; `authorization.md` membership section |
| tenancy ↔ access | Onboarding: `restaurant.created` is handled by access in the same transaction, so there is no dependency cycle | `domain-model.md` rules |
| floor ↔ ordering | Occupancy is maintained by floor on ordering's calls, so floor never queries ordering | `domain-model.md` Table |
| Permissions | Two new codes, `menu.availability` and `owners.manage`. Role defaults for 5 templates. Device-eligibility list | `authorization.md` catalog v1 |
| Tenant boundary | None changed | `tenancy.md` untouched |
| Stale docs | ux-flows F3 (staff "invite", "Invited" status); brief 01 happy path 2 and IA-6; brief 02 happy path 3, RS-1 and RS-7 (C6.11) | not edited (owners: ux-designer, requirements-analyst) |

**Needs the owner's approval (APPROVAL).**
1. Permission catalog v1 (`authorization.md`), including the new codes `menu.availability` (Q48) and `owners.manage` (Q38/Q37), and the reserved Phase 6/8/9 names.
2. Default role templates Owner / Manager / Waiter / Cashier / Kitchen and their matrix (Q9). This includes Manager without `roles.manage`, `settings.manage` or `audit.view`.
3. Device eligibility: the D/P/never lists and the v1 **Kitchen display** profile (`kitchen.view`, `kitchen.update`, plus `menu.view` and `menu.availability` if Q48).
4. Order lifecycle representation: the order stores only open/closed/cancelled, and Q59's preparation states are derived from lines (with Q59).
5. The business-rule questions below (new rules, so APPROVAL). They go to `requirements.md` via requirements-analyst:
   - AQ1: existing user added as staff; the manager never sets their password.
   - AQ2: username scope.
   - AQ3: staff email verification before resets.
   - AQ4: no counter-tablet device profile until PIN switch.
   - AQ5: a device survives removal of the member who paired it.
   - AQ6: RS-1 wording (pending owner invitation).
   - AQ7: audit payloads record "changed" instead of values for staff personal fields (C5 vs C6.8).
   - AQ8: minimization vs Q40's "history keeps the original name".
   - Overlap with Track C2: AQ1 = C2 question 2, AQ2 = C2 question 5, AQ4 = C2 question 3. Ask each once. The domain model uses the C2-recommended answers (invite for existing users; option (b) until PIN).
6. Retention purge after 7 years: deferred, to be designed and approved before 2033.

**REVIEW (surfaced, not blocking).**
- Aligned with Track C2 (written concurrently): pairing uses DV-02 pairing codes, rotation uses DV-04, and eligibility follows DV-01. As an addition, `menu.view`, `menu.availability` and `tables.view` are device-attributed eligible; security-engineer to confirm.
- Same-transaction domain-event handlers as the anti-cycle rule.
- `authorization.md` membership and device text corrected to match C6.11 and C6.12.

**Follow-ups.** C2 conflict "device absolute lifetime" is fixed in `authorization.md`. ux-designer: redo F3 as "Add staff" with an initial password. requirements-analyst: transcribe AQ1–AQ8 and fix the stale brief text. security-engineer: re-check the device-eligibility list and the audit-payload proposal against the threat model.

## Track C2 — Security re-validation (security-engineer, 2026-09-30)

The threat model in `docs/architecture/security.md` is now v2. It is re-validated against the Accepted ADR-0003/0005/0006 with amendments and against C6.11–C6.14. Changed rows: TM-03, TM-05, TM-07, TM-08, TM-09, TM-24 and TM-28. New rows: TM-32..TM-46. New control sets: SP-01..SP-11 (manager-set passwords), PN-01..PN-11 (PIN switch) and DV-01..DV-05 (device sessions). Risks: R7 and R17 updated, R19–R24 added. **Verdict: PROCEED WITH CONTROLS.** No point below is blocking. The identity-schema and staff-management work must not start until questions 1–3 are answered.

### Verdicts on the architect's REVIEW points
| # | Design point | Verdict | Conditions / reason |
|---|--------------|---------|---------------------|
| 1 | `rms_scheduler` DB credential (tenancy.md) | **Accept with conditions** | The CI catalog check asserts its grants are exactly SELECT on registry `id` and `status`, with no DML, no tenant tables, no role memberships and no `BYPASSRLS`. The registry policy that lets it see every row is role-targeted and allow-listed. Timeouts are set as for `rms_app`. The credential exists only in the scheduler environment, and the runtime env check covers it (TM-42). Enqueueing goes through the broker, so the broker is also a trust boundary: job types are allow-listed and job effects are re-derived under RLS (TM-24). |
| 2 | Invite-lookup definer owner with `BYPASSRLS` | **Accept with change (REVIEW → data-engineer)** | `BYPASSRLS` is not needed. The written reason is inaccurate: the definer owner is not the table owner, so ordinary RLS (not `FORCE`) is what applies. That is solved more narrowly by role-targeted SELECT policies (`CREATE POLICY … FOR SELECT TO <definer_owner> USING (true)`) on the invitations table and on the registry, combined with column grants. `BYPASSRLS` applies to every table in the database and is reachable by any role that can `SET ROLE` to the owner. That includes the migrator: in PostgreSQL, `ALTER FUNCTION … OWNER TO` requires the ability to `SET ROLE` to the new owner. Fall back to `BYPASSRLS` only if the Phase 2 spike shows the policy approach fails, and record why. Either way: `REVOKE EXECUTE … FROM PUBLIC` (PostgreSQL grants it by default), grant it to `rms_app` only; pinned `search_path` with `pg_temp` last and schema-qualified names; no dynamic SQL; fixed-length hash input and a unique index; the body hash is pinned in the CI allow-list; the owner role has no runtime members (TM-41). |
| 3 | User-scoped membership policy only when no tenant is set (C3-1a) | **Accept** | Permissive policies are OR-ed. With `app.tenant_id` set, the second policy is false, so a tenant-plane query is not widened. It must be `FOR SELECT`. `app.user_id` is set only by the identity entry point, the same way as the tenant context. Recommended (low): list only non-removed memberships, so former staff do not keep seeing the restaurant's name and status. Tests: NT-40. |
| 4 | Tenant UUID in the path | **Accept** | It is better than a slug: no squatting and no rename handling. The UUID is not a secret, and security does not rely on it being one. Parse it, then use only the canonical value for context, cache keys and channels. Malformed, unknown and non-member tenants get the identical 404. Use random (v4) IDs for tenants. A `Referrer-Policy` limits leakage (TM-08). |
| 5 | 409 `tenant_mismatch` only for tenant-bound credentials | **Accept with conditions** | The check runs after the UUID is parsed and before any DB access. It is identical for existing and non-existent tenants, so it is no oracle. It writes nothing and logs a security event. Personal sessions never get 409: the path fixes the tenant per tab, so TM-09 is removed by construction (TM-09, DV-05). |
| 6 | Device eligibility (catalog v1 D/P/never, Track D2) | **Accept (catalog: APPROVAL with Q9)** | The Track D2 list already covers my v1 concerns: `devices.manage`, `staff.view`, `reports.view`, `history.view`, cancel, discount, refund and price codes are never eligible. P codes need PIN switch (PN-01..PN-11). Addition: the server re-checks eligibility on every request, so a later catalog change cannot widen existing devices (DV-01). `menu.availability` as a D code is acceptable if it is audited (Q48). |
| 7 | Pairing method (Track D2 REVIEW) | **Pairing code (DV-02), as now in `authorization.md` / `domain-model.md`** | Both tracks changed this at once, and the final state is consistent. The code is single-use, lasts at most 10 minutes, is stored hashed, is bound to the tenant and profile, is rate-limited on redemption, and the pairer's permissions are re-checked at redemption. Converting a personal session on the tablet is rejected: it puts a manager's password on a shared device (TM-43). |
| 8 | Transparent rotation of the never-expiring device secret (Track D2 REVIEW) | **Required** | Rotate server-side (suggested 24 h, short grace), invisible to staff. Without it a copied device cookie works until someone notices (DV-04, TM-44, R23). |
| 9 | AQ5: a device survives removal of the member who paired it | **Acceptable** | The profile is fixed and capped at pairing, so removing the pairer does not widen it. Recommended: flag that member's devices for review by `devices.manage` holders, without auto-revoking (service continuity). |
| 10 | AQ7: audit records "changed" instead of values for staff personal fields | **Accept with condition** | Fine for name and contact details. Values for authorization state (roles, grants, status, device profile) must be recorded in full (C5). For login identifiers (email/username), record a keyed hash of old and new, so an account-takeover investigation can still match them without storing the plaintext. |

### C6.11 and C6.13 — summary
- **Manager-set passwords (TM-32..TM-36).** The main risks:
  - The manager knows the credential. This is residual (R19). SP-01..SP-06 limit it.
  - Cross-tenant account takeover by resetting an identity that also exists in another restaurant (R20). SP-07/SP-08 prevent it.
  - Pre-account hijacking through a manager-entered email (R22). SP-09 prevents it.
- **PIN switch (TM-37..TM-39).** Rules:
  - A PIN is only a second step on a paired POS device. It is per membership.
  - Staff pick their name, then enter the PIN.
  - Minimum 6 digits, a peppered slow hash, throttling with disablement.
  - Effective permissions are the device's set ∩ the membership's permissions.
  - Switch state is server-side, with auto switch-out.
  - Order and payment commands return 403 `individual_required` when nobody is switched in.
- **Devices and clients (TM-43..TM-46).** Pairing codes, credential rotation (C6.12 gives devices no timeout), no API caching in the service worker, and a capped progressive delay.

### Conflicts found in docs (for the architect; not edited here)
- (Resolved during this track: `authorization.md` now says device sessions are valid until revoked, matching C6.12.)
- `authorization.md` `owners.manage` includes "reset owners". SP-08 recommends that owners are never admin-reset. See question 2.
- `tenancy.md` C3-1c text ("`BYPASSRLS`, because `FORCE` RLS also applies to the definer") should follow verdict 2 once the data-engineer confirms.
- `briefs/01` IA flow 2 and `ux-flows.md` F5 still describe staff email invites. After C6.11 they need a "create staff with password" flow.

### Decisions
- Threat model v2, control sets SP/PN/DV and verdicts 1, 3, 4, 5: `REVIEW` (security-engineer).
- Verdict 2 (replace `BYPASSRLS` with role-targeted policies): `REVIEW` (data-engineer + security-engineer). It narrows a tenant-boundary mechanism the owner already accepted and does not widen it.
- Verdict 6 and DV-01: the catalog part is `APPROVAL` (with Q9). Verdict 7 (pairing code): `REVIEW`.
- Verdicts 8 (rotation required), 9 and 10: `REVIEW`. AQ5 and AQ7 themselves remain `APPROVAL` (business rules).
- SP-01, SP-02, SP-07, SP-08 (owners), PN-04, PN-06, PN-09 timing, DV-04 auto-revocation: `APPROVAL` (new business rules). See the questions below.

### Questions for the human (E)
1. (blocking Phase 2) **Q71.** Staff must change a manager-set password at first login. The temporary password expires unused after 72 h. The manager can reset but never view it. Is the temporary password system-generated and shown once (recommended), or typed by the manager (allowed, under the same policy)?
2. (blocking the Phase 2 identity schema and the Phase 3 staff feature; extends AQ1 and AQ3) **Reset scope.** A manager's reset would apply only to identities their restaurant created, that have no membership elsewhere and are not owners anywhere (SP-07). Otherwise one restaurant's manager could take over an account used in another restaurant (R20). Should owners never be admin-reset, including by other owners through `owners.manage`, and use the email reset or Q34 recovery instead (SP-08)? Recommended: yes to both. For AQ1, security needs only that the existing user consents, for example by accepting an invite. For AQ3, the answer is yes (SP-09).
3. (blocking Phase 2; same as AQ4) **POS attribution in v1.** Either (a) build PIN switch in v1 with PN-01..PN-11, or (b) ship no counter-tablet profile until PIN switch exists, so counter staff use personal logins. Security accepts both. What security rejects is a counter tablet on a long-lived personal session (R17). Recommended: (b) unless counter tablets are needed from day one.
4. (blocking the PIN feature) **PIN rules.** Minimum 6 digits? Disable the PIN after 10 consecutive failures, so the staff member resets it after a password login? Automatic switch-out after 90 s of inactivity?
5. (blocking the Phase 2 identity schema; same as AQ2) **Username scope.** Security view: a platform-wide namespace lets managers find out which usernames exist, a low risk given rate limits and audit (SP-10). A per-restaurant namespace needs a restaurant identifier at login and must never let one restaurant's username log in to another. Either is acceptable with those controls.
6. (non-blocking) **Devices.** Rotate the device credential every 24 h (invisible to staff)? Flag devices not seen for 14 days, and should they be revoked automatically?
7. (non-blocking) **R19.** Do you accept the residual risk that a manager who sets or resets a password can act as that staff member until it is changed, with forced change, audit and notice as mitigation?

## Track A2 — Brief fixes and question transcription (requirements-analyst, 2026-09-30)
Documents only. Nothing was added to "Confirmed".

**Brief fixes for C6.11.**
- `briefs/01-identity-access.md`:
  - update note under the header;
  - new actor row for staff with a manager-set password;
  - happy path 2 is now "Staff account created by a manager";
  - IA-1 test now uses owner invitations;
  - IA-5 and IA-6 rewritten: owners verify, invitation acceptance verifies, staff pending Q74;
  - new IA-22 (initial password sign-in; the password never appears in audit, logs or screens);
  - invite edge cases rewritten; happy path 6 and the counter-tablet edge case now cite C6.13, C6.14 and Q75.
  - No renumbering.
- `briefs/02-restaurant-setup-staff.md`:
  - update note under the header;
  - happy path 3 is now "Create", with the status "Active";
  - RS-1 now reads "pending owner invitation", with a failure test;
  - RS-7 has no "invited" status, and owner invitations are listed separately;
  - RS-9 adds manager password reset and "no password in audit", with personal fields pending Q78;
  - RS-12 says "re-adding";
  - edge cases rewritten.
  - No renumbering.

**Overlap check.** The architect's mapping is right for AQ2 = C2 Q5 and AQ4 = C2 Q3. AQ1 = C2 Q2 is only partly right. C2 Q2 gives the security view on AQ1 (consent through an invitation) and on AQ3 (yes). It also asks two separate things: the manager reset scope (SP-07) and "owners are never admin-reset" (SP-08). Those two became their own question, Q80, which refines Q31. C2 Q1 extends the existing Q71, so it gets no new number.

**Mapping.**
| Source | Q in `requirements.md` |
|---|---|
| AQ1 (+ C2 Q2, AQ1 part) | Q72 |
| AQ2 = C2 Q5 | Q73 |
| AQ3 (+ C2 Q2, AQ3 part) | Q74 |
| AQ4 = C2 Q3 | Q75 |
| AQ5 (+ C2 verdict 9 recommendation) | Q76 |
| AQ6 | Q77 |
| AQ7 (+ C2 verdict 10 condition) | Q78 |
| AQ8 | Q79 |
| C2 Q1 | Q71 (extended: generated vs typed, 72 h expiry) |
| C2 Q2 (SP-07/SP-08 part) | Q80 (Q31 marked "refined by Q80") |
| C2 Q4 | Q81 |
| C2 Q6 | Q82 |
| C2 Q7 | Q83 |

**Blocking.**
- Phase 2: Q71, Q72, Q73, Q74, Q75, Q78, Q80.
- Phase 3: Q77, Q79.
- PIN switch feature: Q81.
- Non-blocking: Q76, Q82, Q83.

**Not changed (follow-ups).**
- Brief 01 still says "pending" for some items already answered by C6.12. These are IA-8, IA-10, IA-11, IA-14 and IA-15 (Q29/Q30), and IA-18 (Q8). They are outside this task's invite scope.
- `ux-flows.md` F3/F5 belong to the ux-designer.

## Track E — documentation sync (tech-writer, 2026-09-30)
Documents only; no code exists (`backend/`, `frontend/` absent), so every claim was checked against `docs/product/requirements.md` C6.1–C6.23 (authoritative) and this record. `requirements.md` and the Accepted ADRs were not edited.

**Changed.**
- `product/briefs/01-identity-access.md`: new update note; happy paths 2, 5, 6; IA-1, IA-5, IA-8, IA-10, IA-11, IA-14, IA-15, IA-18, IA-20, IA-21, IA-22; edge cases (existing identifier, temp password, counter shift change, kitchen reboot, stolen phone); must-have list; open-question lists marked answered.
- `product/briefs/02-restaurant-setup-staff.md`: update note; happy paths 2, 3, 6; RS-9 (C6.22), RS-12, RS-13; edge cases; open-question lists.
- `product/briefs/03-menu.md`, `04-tables.md`, `05-orders-kitchen.md`: answered Q7/Q9/Q19/Q33 references (C6.4, C6.7, C6.13, C6.17, C6.19).
- `product/ux-flows.md`: status; F1 (verify-email screen owners only, C6.21); F3 (C6.15/16/18/20/21/23; email hint "Contact information only"; no existing-user path; reset scope; PIN text deferred); F4/F5/F7/F8 dependency labels; F8 marked Planned (C6.17).
- `architecture/domain-model.md`: status; Staff account and Device profile terms; Membership create/reset rows and invariants (C6.15, C6.16, C6.18, C6.20, C6.23); device invariants (C6.17, Q76); open-items list with AQ1–AQ8 status.
- `architecture/authorization.md`: status line (catalog and roles approved, eligibility Proposed); staff creation and password rules (C6.15, C6.16, C6.20, C6.21, C6.23); v1 device profile note (C6.17); catalog dependency table.
- `architecture/security.md`: control 4; threat-model status; E3/E14; TM-34/NT-34 and TM-35; SP-01, SP-02, SP-04, SP-05, SP-07, SP-08, SP-11 marked with deciding C-numbers; SP-09 kept in full with a "v1 applicability" note (verification clause **not applicable in v1, C6.21**); PN section labelled Planned (C6.17); DV-01, DV-04; residual risks. No control removed or weakened.
- `risks.md`: R7, R17, R20, R21, R22, R23 status/mitigation text.
- `architecture/data.md`, `architecture/audit-logging.md`: C6.22 audit payload rule; audited access events (no "membership invited").
- `architecture/overview.md`: identity row (catalog v1 approved). `conventions/frontend.md`: Q21/Q23 answered.
- `CHANGELOG.md`: Unreleased entries for change 0002.

**Could not reconcile (need an owner answer or the owning agent).**
1. C6.4 vs C6.21: C6.4 lets staff sign in with email or username; C6.21 says a staff email is "contact information only". Whether a staff email may be a login identifier is unclear. Docs now say "contact information only" and do not claim staff email sign-in either way (ux-flows F1 still says "email or username, C6.4").
2. C6.16 vs Q80: C6.16 says owners are never reset by *managers*; Q80 (marked answered → C6.16) also asked about other owners via `owners.manage`. `authorization.md` `owners.manage` still lists "reset owners"; flagged as open there, in `domain-model.md` and in SP-08.
3. Q41 (re-hire) vs C6.20: re-adding a removed person whose User still exists is "adding an existing user as staff", which C6.20 forbids. Flagged in brief 02 RS-12 and the domain-model re-hire row.
4. Owner invitation to an email that an existing staff account holds as unverified contact info (C6.20 allows owner invitations for existing users; SP-09/TM-07 require a verified email; C6.21 gives staff no verification path). The invite cannot be accepted by that account in v1; the intended outcome is not decided.
5. Device eligibility: `security.md` DV-01 lists `orders.view` as D; `authorization.md` marks it P. Not changed (eligibility list is still Proposed, APPROVAL).
6. Q48 is not marked answered in `requirements.md`, though C6.19 approved the `menu.availability` code and its Kitchen/Manager defaults. Docs say "code approved (C6.19); audit and Kitchen display inclusion remain with Q48".

**Follow-ups (not edited; other owners).**
- ADR-0006 amendment C6-7 still says UX-5 is open (answered, C6.14); ADR-0005 follow-up line cites Q9 (answered, C6.19). Accepted ADRs are not edited; a note or superseding text is the architect's call.
- `product/roadmap.md` Phase 2 bullets say "signup/invite" and exit "sign up/accept invite"; with C6.6/C6.11 there is no self-service signup and staff are created by managers (orchestrator; human approves).
- `conventions/api.md` CSRF line lists anonymous "signup" POSTs (no self-service signup in v1, C6.6) and has no staff-create/reset endpoints yet (architect).
- `requirements.md` Q72/Q74 rows keep their superseded suggested defaults ("receives an invitation", "unverified until the staff member verifies it") next to "Answered"; harmless but could mislead (requirements-analyst).
- Security-engineer re-run of the threat model against C6.15–C6.23 (noted in `security.md` status).

## 12. Acceptance
Exit criteria in `roadmap.md` Phase 1.
