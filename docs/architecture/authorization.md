# Identity, Membership and Authorization

**Status:** Model accepted (ADR-0005; sessions and devices per ADR-0006 with amendments C6-1..C6-8; product owner, 2026-09-30, change 0002). Permission catalog v1 and the default role templates are Approved (C6.19); the device-eligibility list and the Kitchen display device profile are still Proposed. Adding or changing codes is `APPROVAL`. Nothing is built yet. Owner: `security-engineer` + `architect`.

## Concepts
```
User (identity, platform-level)
  └─< Membership (user × restaurant, status)
         ├─< MembershipRole  ──> Role (restaurant-scoped; from system template or custom)
         │                        └─< RolePermission ──> Permission (global catalog code)
         └─< MembershipPermission (direct grant — used sparingly, audited)
```
- A user may hold memberships in several restaurants. Each **request** acts through exactly one membership: the user's membership in the restaurant named in the URL path, validated on every request (`tenancy.md`, ADR-0006 C6-2). The session stores only a default (last-used) restaurant for landing redirects, so two tabs on two restaurants cannot retarget each other's writes.
- Effective permissions = union of that membership's role permissions + direct grants. (Deny rules are not supported in v1: simpler and predictable.)
- The **owner** role is a system role with all permissions; it cannot be edited, and a restaurant always has ≥ 1 active owner.
- System role templates (approved, C6.19) are copied into each restaurant as editable roles on creation, except Owner.

## Enforcement
- One server-side helper, e.g. `require(permission_code)` at the handler plus `authorize(principal, code, obj=None)` in services for object-level rules. The principal is the request's membership or a device session (below).
- Default deny: handlers without a declared permission fail a test that scans all routes.
- Checks use permission codes, never role names.
- Effective permissions are computed per request (cacheable per request only); revocation takes effect on the next request.
- Frontend receives the effective permission list for display only.

## Escalation guards
- You can grant only permissions you hold, and only if you hold `staff.manage` (or the relevant code).
- You cannot change your own roles/permissions.
- You cannot modify, suspend or remove an owner unless you are an owner.
- The last active owner cannot be removed or demoted.
- All grants/revocations are audit events.

## Membership lifecycle and retention
- States: active → suspended → removed (`domain-model.md`, change 0002 Track D2). There is no `invited` membership state: staff accounts are created directly by a member with `staff.manage`, who hands over a system-generated temporary password (C6.11, C6.15); owners join through a separate **Invitation** entity (pending → accepted / revoked / expired, C6.6) whose acceptance creates an active membership. Only `active` passes tenant resolution. Every other state returns 404 on the restaurant's paths from the next request on (TM-05).
- Staff account creation (C6.11) always creates a new User. An email or username that already belongs to a User is refused, and the message never names another restaurant (C6.20); staff creation therefore never sets or overwrites an existing User's password. An existing User joins another restaurant only as an owner, by invitation (C6.6). The model still allows one User in several restaurants (C2.4).
- Staff passwords (C6.15, C6.16): the temporary password is system-generated, shown once, must be changed at first login and expires unused after 72 h. A holder of `staff.manage` may reset (never view) the password only of accounts their restaurant created that have no membership in any other restaurant and are not an owner anywhere. Owners are never reset by managers; they use the email reset link. Every reset is audited and ends the person's sessions. The staff email is contact information only: no verification, no reset link, no account email (C6.21).
- Residual risk R19 (a manager can act as a staff member until the temporary password is changed) is accepted by the owner (C6.23).
- Retention (Q20, product owner 2026-09-30): orders, payments and audit events are kept for 7 years. The staff member's personal data is minimized after membership removal. Audit events and orders keep the membership ID as the actor, so history stays attributable without keeping more personal data than needed.
- Open (non-blocking for Phase 2 design, blocking for the removal feature): which fields are minimized, when, and how an actor is displayed afterwards. The rules belong in `requirements.md`. The mechanism is the data-engineer's job.

## Authentication and sessions (ADR-0006, amended)
- **Personal login** (Q6): email/username plus password, as a server-side session. The cookie is `__Host-`, `HttpOnly`, `Secure`, `SameSite=Lax` or stricter, has no `Domain`, and holds only the session ID. It runs on a single host with the restaurant in the path (C6-1).
- **Session store** (C6-4/C6-5): a PostgreSQL platform-level table, used only by the identity module. Each row has `user_id`, a hashed session key, `created_at` and `last_seen_at`, used for idle and absolute timeouts (values fixed in Phase 2). Serialization is JSON only.
- **Revocation:** a password change/reset or email change deletes all of the user's sessions. "Log out everywhere" does the same. Membership, role and tenant-status changes take effect on the next request, through per-request evaluation.
- **Rotation** (C6-8): the session ID rotates on login, restaurant switch, and password or MFA change.
- **CSRF** (C6-3): enforced on every unsafe method, including anonymous login, signup, reset and invite-accept POSTs. `CSRF_TRUSTED_ORIGINS` is strict. No GET has side effects.
- **MFA** (Q8): TOTP is optional for owners and mandatory for platform operators. Enabling or disabling MFA is audited and rotates the session. Open: whether non-owner staff may enable TOTP, and the recovery method (recovery codes, or reset by the owner or operator).
- **Operator console** (C6-7, Q5): a separate host and cookie name, mandatory MFA and a short absolute timeout. It never uses tenant endpoints.

## Device sessions (Q7 = yes; ADR-0006 C6-7)
- A **device session** is a separate credential type for shared kitchen/counter tablets. It is not a personal session and not a membership.
- It is bound to exactly one restaurant, at pairing. Its path tenant must equal that restaurant, otherwise 409 `tenant_mismatch`.
- It carries a **fixed, limited permission set** (a device profile) chosen at pairing from device-eligible catalog codes (see "Device eligibility" below; still Proposed, `APPROVAL`).
- It has no idle logout and no absolute expiry: it is valid until revoked (C6.12). It can be revoked per device, taking effect on the next request, and open streams close. It also stops working while the restaurant is not `active`. The credential rotates server-side (security DV-04; interval pending the owner, Q82).
- Pairing follows security DV-02: a single-use pairing code issued in a personal session with `devices.manage` and entered on the device. The profile is capped by the eligible list and by the pairer's own permissions (`domain-model.md`, `security.md`).
- Ownership: the device registration (name, permission set, paired-by membership, status) is tenant-owned, in the `access` context. The session row lives in the identity session store with a device kind and the bound `tenant_id`.
- Audit: the actor is the device, plus the membership that paired it. When PIN quick-switch arrives (later, C6.4, C6.17), the actor becomes the switched-in membership.
- v1 has only the Kitchen display device profile; there is no counter/POS device profile (C6.17).
- Pairing and revoking are audited commands requiring `devices.manage` (UX-5, product owner 2026-09-30; C6.14).

## Permission catalog v1 — Approved (product owner, 2026-09-30, C6.19)
**Status: Approved** — codes and default role templates (C6.19, 2026-09-30); `devices.manage` (C6.14). Device-eligibility list and the Kitchen display profile approved (C6.25, 2026-09-30); `orders.view` is PIN-only (P), not device-eligible in v1. Change 0002, Track D2. Replaces the v0 draft. Adding, removing or renaming a code, the device-eligibility list and the role defaults below are all `APPROVAL`. Codes are `<resource>.<action>`, checked through `authorize`, never by role name.

Phase column: codes for Phases 6, 8 and 9 are **reserved names**. They are listed so that roles look complete, and each is confirmed when its phase starts (Q14, Q16, Q17).

Device column: **D** = device-eligible, attributed to the device (C6.13). **P** = eligible only with an individual switched in by PIN (C6.13; PIN is later, C6.4, so not usable by devices in v1). **—** = never on a device.

| Group | Code | Grants | Phase | Device | Depends on |
|---|---|---|---|---|---|
| Dashboard | `dashboard.view` | See the dashboard | 3 | — | |
| Orders | `orders.view` | See orders and their line status | 5 | P | |
| | `orders.create` | Start an order and send rounds | 5 | P | Q60 |
| | `orders.update` | Mark served, move table, edit notes, void a line **before** preparation, close (v1) | 5 | P | Q59, UX-3, Q55, Q61 |
| | `orders.cancel` | Cancel an order; void a line **after** preparation started (reason mandatory) | 5 | — | Q61/UX-2, Q62 |
| | `orders.discount` | Apply discounts | 6 | — | Q14, Q15 |
| Kitchen | `kitchen.view` | See the kitchen board | 5 | D | |
| | `kitchen.update` | Start, ready, undo on tickets/lines | 5 | D | Q63, UX-3 |
| Billing | `billing.view` | See bills | 6 | P | Q14 |
| | `billing.take_payment` | Record payments | 6 | P | Q14 |
| | `billing.refund` | Refunds | 6 | — | Q14 |
| Menu | `menu.view` | See the menu (also needed to order) | 4 | D | |
| | `menu.manage` | Create, edit, reorder, archive, delete items/categories/modifiers | 4 | — | Q49, Q45 |
| | `menu.price_change` | Change prices (money-affecting, separate from manage) | 4 | — | Q50 |
| | `menu.availability` | **New.** Mark items sold out / available (code approved, C6.19) | 4 | D | Q48 |
| Tables | `tables.view` | See the table view | 4 | never (v1, C6.25) | |
| | `tables.manage` | Configure tables/areas; set out of service | 4 | — | Q54, Q53 |
| Inventory | `inventory.view`, `inventory.adjust`, `inventory.manage` | Reserved | 8 | — | Q16 |
| Reservations | `reservations.view`, `reservations.manage` | Reserved | 9 | — | Q17 |
| Reports | `reports.view` | Reports | 7 | — | |
| | `history.view` | Past (closed/cancelled) orders | 5 | — | Q69 |
| Staff | `staff.view` | See staff list and roles | 3 | — | |
| | `staff.manage` | Create staff accounts, assign roles, suspend/reactivate/remove, reset password and end sessions of **non-owners** (reset scope C6.16) | 3 | — | C6.15, C6.16, Q31, Q40, Q41 |
| | `roles.manage` | Create/edit/delete custom roles | 3 | — | Q42 |
| | `owners.manage` | **New.** Invite, suspend, remove, demote, reset owners; held only by the Owner role, never grantable. Owners are never reset by managers (C6.16); whether "reset owners" stays in this code is open (change 0002, Track E) | 3 | — | **Q38**, Q37, C6.16 |
| Settings | `settings.view` | See restaurant settings | 3 | — | |
| | `settings.manage` | Change restaurant settings, including money settings | 3 | — | Q37 |
| | `devices.manage` | Pair, rename, revoke shared devices (approved, C6.14) | 2 | — | |
| Audit | `audit.view` | Read the audit log | 3 | — | |

Why `owners.manage`: the guard "only an owner may act on an owner" (Escalation guards) otherwise needs a role-name check, which the rules forbid. A non-grantable code keeps every check code-based.

### Device eligibility
- **D** codes may appear in a device profile in v1: exactly `kitchen.view`, `kitchen.update`, `menu.view`, `menu.availability` (C6.25, product owner 2026-09-30). `orders.view` is **P** (future PIN counter profile); `tables.view` is not device-eligible in v1. Matches `security.md` DV-01.
- **P** codes are for a future counter-tablet profile with PIN switch. No such profile exists in v1 (C6.17). The effective set then is the device set ∩ the switched-in member's permissions.
- Everything else is never device-eligible. That includes all staff, roles, owners, settings, devices, audit, reports, history, refund, cancel, discount and price codes (matches DV-01).
- v1 profile **Kitchen display** (Proposed; the only v1 profile, C6.17): `kitchen.view`, `kitchen.update`. With Q48's suggested default, it also gets `menu.view` + `menu.availability`, so cooks can mark sold out.

### Default role templates — Approved (C6.19, 2026-09-30)
● = granted. Owner holds every code, including reserved ones, and cannot be edited. The others are copied into each restaurant as editable roles (C6.19).

| Code | Owner | Manager | Waiter | Cashier | Kitchen |
|---|:-:|:-:|:-:|:-:|:-:|
| `dashboard.view` | ● | ● | | | |
| `orders.view` | ● | ● | ● | ● | |
| `orders.create` | ● | ● | ● | ● | |
| `orders.update` | ● | ● | ● | ● | |
| `orders.cancel` | ● | ● | | | |
| `orders.discount` (6) | ● | ● | | | |
| `kitchen.view` | ● | ● | | | ● |
| `kitchen.update` | ● | ● | | | ● |
| `billing.view` (6) | ● | ● | | ● | |
| `billing.take_payment` (6) | ● | ● | | ● | |
| `billing.refund` (6) | ● | ● | | | |
| `menu.view` | ● | ● | ● | ● | ● |
| `menu.manage` | ● | ● | | | |
| `menu.price_change` | ● | ● | | | |
| `menu.availability` | ● | ● | | | ● |
| `tables.view` | ● | ● | ● | ● | |
| `tables.manage` | ● | ● | | | |
| `inventory.*` (8) | ● | ● | | | |
| `reservations.view` (9) | ● | ● | ● | ● | |
| `reservations.manage` (9) | ● | ● | | | |
| `reports.view` | ● | ● | | | |
| `history.view` | ● | ● | | ● | |
| `staff.view` | ● | ● | | | |
| `staff.manage` | ● | ● | | | |
| `roles.manage` | ● | | | | |
| `owners.manage` | ● | | | | |
| `settings.view` | ● | ● | | | |
| `settings.manage` | ● | | | | |
| `devices.manage` | ● | ● | | | |
| `audit.view` | ● | | | | |

Notes on the defaults (each is part of the Q9 approval, C6.19):
- Manager: no `roles.manage` (Q42 suggested: role editing owner-only), no `settings.manage` (Q37: the template keeps settings with the owner; an owner can grant it), no `audit.view` (the audit log shows staff actions, so owner-only by default). Holding `staff.manage`, a manager can assign any role whose codes they hold, including Manager itself.
- Waiter: no billing (Q14: whether waiters present or collect the bill is Phase 6). Cashier holds `history.view` for receipt look-ups.
- Kitchen (the personal role for cooks on phones): the same codes as the Kitchen display profile.

### Where the catalog depends on open questions
| Question | Effect on the catalog if the answer differs from the suggested default |
|---|---|
| Q9 | Answered (C6.19): role templates approved as above |
| Q48 | The code is approved (C6.19); whether availability changes are audited (suggested yes) and whether the Kitchen display profile includes it remain with Q48 |
| Q42 | Whether Manager gets `roles.manage` |
| Q37 | Whether money settings need a separate code (e.g. `settings.money`), and whether Manager gets `settings.manage` |
| Q38 | `owners.manage` scope: several owners, and demotion by owners |
| Q31, Q71, Q80 | Q71 and Q80 answered (C6.15, C6.16): manager reset stays in `staff.manage`, limited to accounts the restaurant created with no membership elsewhere and no owner role anywhere. Q31 (ending sessions without a reset) is open |
| Q61 / UX-2, Q62 | Void after preparation shares `orders.cancel`. A split (`orders.void`) would let a restaurant allow voids without full cancel |
| Q59 / UX-3 | If kitchen may mark served, `kitchen.update` also covers ready → served |
| Q54, Q55 | Out of service under `tables.manage`; moving an order under `orders.update` |
| Q14, Q15, Q16, Q17 | Reserved codes confirmed or changed when the phase starts |
| Q43 | Direct grants use the same codes; UI exposure only |
| Q75 | Answered (C6.17): no counter-tablet profile in v1, so **P** codes are unused until PIN switch |
