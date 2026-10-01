# Domain Model

**Status:** Mixed, per section (change 0002, Track D2). Sections marked **Accepted** (product owner, 2026-09-30, change 0002) rest only on Confirmed requirements (C1–C6.23) and accepted ADRs 0003/0005/0006 (synced to C6.15–C6.23 in change 0002, Track E). Sections marked **Proposed** use the suggested default of the open questions they name and change if the answer differs. Inside a Ready section, a row tagged `[Qn]` is Proposed. No schemas: `data-engineer` designs them per feature. Owner: `architect`.

Enforcement points: **DB** = constraint (NOT NULL, CHECK, UNIQUE, FK, partial unique, RLS). **Svc** = the owning context's service, inside the command's transaction. **Entry** = the tenant-transaction entry point (`tenancy.md`). Every status change is an explicit command, never a writable `status` field. Every tenant-owned row belongs to exactly one tenant (DB: RLS + composite FK, `tenancy.md`).

## Ubiquitous language — Accepted (2026-09-30)

| Term | Meaning |
|------|---------|
| **Platform / Platform operator** | The business that sells RMS, and its staff. Not a tenant. Operators create restaurants and owner invitations (C6.6) and never use tenant endpoints. |
| **Restaurant / Tenant** | One restaurant location (C6.2); the isolation boundary for all operational data. Has a status (below). |
| **User** | A person's identity: login identifier (email or username, C6.4), password, optional TOTP (C6.5), verified email if any. Platform-level; belongs to no restaurant by itself. |
| **Staff account** | Name for the creation path in C6.11: a manager creates a **new** User with a system-generated temporary password (C6.15) **and** an active Membership in their restaurant, in one transaction. Never used for an email or username that already belongs to a User (C6.20). The staff email is contact information only (C6.21). Not a separate entity. |
| **Invitation** | An emailed, single-use, expiring offer of a membership, accepted by the invitee. In v1 used for owners (C6.6); staff are not invited (C6.11). Accepting verifies the email (C2.6). |
| **Membership** | A user's participation in one restaurant. Status active / suspended / removed. All personal authorization hangs off it. |
| **Owner** | A membership holding the protected Owner role. |
| **Staff member** | Any non-owner membership. |
| **Role / System role template** | A named permission set within a restaurant. Templates (Owner, Manager, Waiter, Cashier, Kitchen; approved, C6.19) are platform-level and copied into each new restaurant as editable roles, except Owner (not editable). |
| **Permission / Permission group** | A global code `<resource>.<action>` granting one capability; groups are UI grouping only (`authorization.md`). |
| **Principal** | Whoever a request acts as: a membership (personal session) or a device. |
| **Device** | A shared restaurant tablet paired to one restaurant with a fixed permission set (C6.4, C6.14). Tenant-owned registration in `access`. |
| **Device session** | The credential a paired device holds. Identity session store, bound to one tenant, no idle timeout, valid until revoked (C6.12). Not a membership. |
| **Device profile** | The named fixed permission set chosen at pairing. v1: *Kitchen display* only (C6.17); its code set is Proposed (not covered by the C6.19 catalog approval; Q48). |
| **Menu item / Category / Modifier group** | Sellable things and their structure; modifiers per Q45. |
| **Availability** | Whether an active item can be newly ordered now: available or sold out. Distinct from archived. |
| **Table / Area** | Physical seating; areas optional (Q53). |
| **Occupancy** | Derived: a table is occupied while it has at least one open order. Never set by hand. |
| **Out of service** | Manual table state blocking new orders (Q54). |
| **Draft** | Unsent lines held on the client. Not a server entity in v1 (UX-6). |
| **Order** | One party's request for items (table or takeaway, Q10), from first send to closed or cancelled. |
| **Order line** | One item × quantity with snapshots of name, unit price and modifiers at the time it was added (Q50). |
| **Kitchen ticket** | The lines sent in one send ("round", Q60); what the kitchen display shows. |
| **Void / Cancel** | Void removes a sent line (Q61, UX-2); cancel ends a whole order (Q62). |
| **Business day** | The reporting/numbering day with a configurable cut-off (Q44). |
| **Bill / Payment** | What is owed and paid (Phase 6, Q14). |
| **Stock item / Stock movement** | Inventory items and append-only quantity changes (Phase 8). |
| **Reservation** | A booking of a table/party for a time (Phase 9). |
| **Audit event** | Immutable record of a business-critical or security action (C5, `audit-logging.md`). |

## Bounded contexts and dependencies — Accepted (2026-09-30)

| Context | Owns | Depends on (calls / listens to) |
|---------|------|------------|
| **identity** | Users, credentials, email verification, password reset, MFA, session store (personal and device sessions) | — |
| **tenancy** | Restaurant registry and status, restaurant settings (timezone, currency, business-day cut-off) | identity |
| **access** | Invitations, memberships, roles, role templates copy, direct grants, device registrations, the `authorize` helper, `me`/restaurant list (identity plane) | identity, tenancy |
| **catalog** | Categories, items, modifiers, availability, prices | tenancy, access |
| **floor** | Areas, tables, out-of-service state, occupancy | tenancy, access |
| **ordering** | Orders, lines, kitchen tickets, voids, cancellations | catalog (read, snapshot), floor (occupy/release), tenancy, access |
| **billing** (Phase 6) | Bills, payments, tax/service charge, receipts | ordering |
| **inventory** (Phase 8) | Stock items, movements, counts | catalog (read), ordering (events) |
| **reservations** (Phase 9) | Reservations | floor |
| **reporting** | Read models over other contexts; no writes | all (read-only) |
| **audit** | Audit events store and query | all (receive) |

Rules:
- Dependencies point one way, no cycles. An upstream context never calls a downstream one; it emits a domain event that the downstream context handles. The handler runs **in the same transaction** when the rule needs atomicity, otherwise through the outbox (realtime, jobs).
- Onboarding (RS-1): the operator command in `tenancy` creates the restaurant and emits `restaurant.created`. `access` handles it in the same transaction: copies role templates and creates the owner invitation. The restaurant is never persisted without its owner invitation.
- Login lives in `identity` and returns a session only. The membership list and restaurant switcher are `access` endpoints in the identity plane (`tenancy.md`), so `identity` never depends on `access`.
- Every tenant context calls `access.authorize(principal, code, obj)`; `access` is the only place that evaluates grants.
- Cross-context writes go through the owning context's service. Every context except identity and the platform side of tenancy is tenant-scoped.

## Lifecycles and invariants

### Restaurant (tenant) status — Proposed (Q39, Q3)
Platform plane; operator console only, MFA mandatory (C6.5), every transition audited with the operator as actor.

| From → To | Command | Who | Side effects | Dep. |
|---|---|---|---|---|
| — → active | create restaurant | operator | `restaurant.created` → owner invitation + role copies (same tx) | C6.6 |
| active → suspended | suspend | operator | Tenant resolution refuses all paths (404) from the next request; device sessions stop working; open streams close | Q3 (reasons) |
| suspended → active | reinstate | operator | Access resumes; nothing else changes | Q3 |
| active/suspended → closed | close | operator | Terminal. Data kept per C6.8; no tenant path works; purge only after retention (`data.md`) | Q39 |

Invariants: status is one of the known values (DB CHECK). Only `active` passes tenant resolution (Entry). The app role reads only `id`, `name`, `status` of the registry (DB grants, C3-1a). Status changes only via the platform plane (DB: app role has no UPDATE on status; Svc).

### Invitation — Accepted (2026-09-30) (owner invitations, C6.6)
| From → To | Command | Who | Side effects | Dep. |
|---|---|---|---|---|
| — → pending | invite owner | operator at onboarding; an owner for additional owners `[Q38]` (`owners.manage`) | Email with single-use token; token stored hashed | C6.6 |
| pending → accepted | accept (POST, CSRF) | invitee, email matched to verified email (TM-07) | Creates an **active** owner membership; email verified; audit | C2.6 |
| pending → revoked | revoke | issuer's authority (`owners.manage`) or operator | Link stops working | `[Q28]` |
| pending → expired | time | system | Link stops working | `[Q28]` 7 days |
| pending → pending (new token) | resend | as revoke | Previous token invalid | `[Q28]` |

Invariants: at most one pending invitation per (tenant, email) (DB partial unique). Token single-use (Svc + DB unique on hash). Lookup only through the C3-1c definer function (DB). Accepted/revoked/expired are terminal (Svc).

### Membership — Accepted (2026-09-30)
There is no `invited` membership state: an invitation is its own entity and staff are created directly (C6.11).

| From → To | Command | Permission | Side effects | Dep. |
|---|---|---|---|---|
| — → active | create staff account | `staff.manage` | identity creates a new User with a system-generated temporary password shown once; must change at first login; unused temporary password expires after 72 h; roles assigned within guards; audit | C6.11, C6.15; refused if the email/username already belongs to a User (C6.20) |
| — → active | accept owner invitation | invitee | see Invitation | C6.6 |
| active → suspended | suspend | `staff.manage`; `owners.manage` if target is owner | Refused from the next request (Entry); open orders untouched `[Q40]`; audit | |
| suspended → active | reactivate | as suspend | Same roles as before; audit | |
| active/suspended → removed | remove | as suspend | Terminal. Personal data minimized per `data.md`; history keeps the membership ID; audit | C6.8; `[Q40]` |
| removed → (new membership) | re-hire | `staff.manage` | New membership, fresh roles; old one stays for history | `[Q41]`; conflicts with C6.20 (an existing User cannot be added as staff) unless Q41 is answered otherwise — open |
| role/grant change | assign / revoke | `staff.manage` (+ `roles.manage` to edit roles) | Effective next request; audit | |
| reset password / end sessions | reset | `staff.manage`, only for accounts this restaurant created that have no membership elsewhere and are not an owner anywhere (C6.16) | New temporary password shown once (C6.15); identity ends all the user's sessions; audit; notice at the staff member's next sign-in (C6.23) | C6.15, C6.16; owners are never reset by managers and use the email reset link (C6.16); whether another owner may admin-reset an owner through `owners.manage` is not stated in C6.16 (open); end sessions without a reset `[Q31]` |

Invariants:
| Invariant | Enforcement |
|---|---|
| At most one non-removed membership per (tenant, user) | DB partial unique |
| Only `active` memberships pass tenant resolution | Entry |
| From first acceptance on, ≥ 1 active owner per restaurant (last owner cannot be suspended, removed or demoted) | Svc, locking the restaurant's owner memberships |
| Nobody changes their own roles or grants | Svc |
| A grant or role assignment contains only permissions the actor holds | Svc |
| Owner role is not editable; `owners.manage` is held only by the Owner role | Svc (+ DB flag on system role) |
| Staff creation never targets an existing User: an email or username that already belongs to a User is refused, and the message never names another restaurant (C6.20) | Svc + DB unique identifiers (usernames unique platform-wide, C6.18) |
| A manager resets only accounts their restaurant created that have no membership elsewhere and are not an owner anywhere; never an owner (C6.16) | Svc |

### Device and device session — Accepted (2026-09-30) (C6.4, C6.12, C6.13, C6.14, ADR-0006 C6-7)
Pairing flow (security DV-02, `security.md`): a member with `devices.manage` starts pairing in their personal session and gets a single-use pairing code (≤ 10 min, stored hashed). The code is entered on the tablet by POST. `access` creates the device registration and asks `identity` to issue a device session. No personal credential is typed on the shared device. The device credential rotates server-side (DV-04).

| From → To | Command | Permission | Side effects | Dep. |
|---|---|---|---|---|
| — → pairing | start pairing | `devices.manage` (personal session) | Pairing code issued; audit | C6.14 |
| pairing → active | enter code on device | holder of the code | Registration (name, profile, paired-by membership); device session issued; code consumed; audit | profile Proposed (device eligibility not covered by C6.19) |
| pairing → (discarded) | code expires or is cancelled | system / pairer | Nothing issued | DV-02 |
| active → active | rename | `devices.manage` | Audit | |
| active → revoked | revoke | `devices.manage`, from any session | Terminal. Device session deleted; next request refused; streams close; audit | C6.14 |
| active → revoked | sign out on the device | device itself | Same as revoke; re-pair creates a new registration | |

Invariants:
| Invariant | Enforcement |
|---|---|
| Bound to exactly one tenant; path tenant ≠ bound tenant → 409, no write | Entry |
| Permission set is fixed at pairing, contains only device-eligible codes (`authorization.md`) and is capped by the pairer's own permissions | Svc |
| Effective permissions = the device set only, never the pairing member's | Svc (`authorize`) |
| No idle timeout, no absolute expiry; valid until revoked (C6.12) or the tenant leaves `active` | identity + Entry |
| Actions are attributed to the device (C6.13) | Svc (audit actor) |
| Orders and payments on a counter tablet need an individual actor (C6.13); v1 has no counter/POS device profile (C6.17), so v1 device profiles hold no order-taking or payment codes | Svc |
| Removing the pairing member does not revoke the device | Svc `[Q76]` |

### Menu item availability — Proposed (Q48, Q49, Q47, Q66)
Two orthogonal attributes: lifecycle (active / archived) and availability (available / sold out, meaningful only while active).

| From → To | Command | Permission | Side effects | Dep. |
|---|---|---|---|---|
| — → active, available | create | `menu.manage` | Visible to ordering; audit | |
| available ⇄ sold out | mark sold out / available | `menu.availability` | `menu.availability_changed` → ordering screens; audit | Q48 |
| active → archived | archive | `menu.manage` | Hidden from ordering; history keeps snapshots; audit | Q49 |
| archived → active | restore | `menu.manage` | Returns as available | Q49 |
| (never ordered) → deleted | delete | `menu.manage` | Hard delete; audit | Q49 |
| price change | change price | `menu.price_change` | New lines only; audit old/new | Q50 |

Invariants: price ≥ 0 in currency precision (DB CHECK; zero per Q51). Item belongs to exactly one category of the same tenant (DB composite FK). An item referenced by any order line is never deleted (DB FK RESTRICT + Svc). Sold-out or archived items, or items in an archived category, cannot be put on a **new** line (Svc in ordering, re-checked at send; whole send refused per Q66). A category with items cannot be deleted (DB FK RESTRICT + Svc). Concurrent edits use a version (Svc, 409).

### Table — Proposed (Q54, Q55, Q56, Q12)
Manual state: in service / out of service / deactivated. Occupancy is derived and never stored as a manual state.

| From → To | Command | Permission | Side effects | Dep. |
|---|---|---|---|---|
| — → in service | create | `tables.manage` | Audit | |
| in service ⇄ out of service | set out of service / back | `tables.manage` | Blocks new orders; open orders unaffected; audit | Q54 |
| in service/out of service → deactivated | deactivate | `tables.manage` | Only with no open order; history keeps name as at order; audit | Q56 |
| (no history) → deleted | delete | `tables.manage` | Hard delete; audit | Q56 |
| free → occupied → free | occupy / release | ordering (via floor service, same tx) | `table.occupancy_changed` → table views | Q54 |
| order moves A → B | move | `orders.update` | Release A, occupy B atomically; audit | Q55 |

Invariants: name unique per (tenant, table) among non-deactivated tables (DB partial unique, Q56). Seats ≥ 1 (DB CHECK). New orders only on in-service tables (Svc in floor, row lock on the table during occupy). A table with an open order cannot be deactivated or deleted (Svc in floor, same row lock; occupancy is maintained by floor on ordering's calls, so floor never queries ordering). Several open orders per table allowed (Q12); no unique constraint.

### Order — Proposed (Q59, Q60, Q61, Q62, Q69, Q10, Q14)
Recommendation (REVIEW): the order stores only open / closed / cancelled. Preparation progress (Q59's "in preparation, ready, served") is a summary derived from its lines. With several tickets per order (Q60), a single stored order-level preparation state would contradict its lines. If Q59 wants those names on screen, they are this summary.

| From → To | Command | Permission | Side effects | Dep. |
|---|---|---|---|---|
| — → open | send (first round) | `orders.create` | Order + lines + ticket in one tx; idempotency key; occupy table; `order.sent` → kitchen | Q59, Q10 |
| open → open | send another round | `orders.create` | New ticket; existing lines keep status | Q60 |
| open → open | move table, notes, mark served | `orders.update` | See Table / Line | Q55 |
| open → closed | close | `orders.update` (v1); after Phase 6 follows payment (`billing.take_payment`) | Only when every line is served or voided; release table; audit | Q59, Q14 |
| open → cancelled | cancel | `orders.cancel` + mandatory reason | All non-served lines voided; release table; `order.cancelled` → kitchen; audit | Q62 |
| closed → open | reopen | not allowed in v1 | — | Q69 |

Invariants:
| Invariant | Enforcement |
|---|---|
| An order is created with ≥ 1 line | Svc |
| One send creates exactly one order/ticket per idempotency key | DB unique (tenant, key) + Svc |
| Closed and cancelled are terminal; their lines are immutable | Svc |
| Totals are computed by the server from line snapshots; client totals are ignored | Svc |
| Concurrent changes: second writer gets 409 | Svc (version column) |
| Table and lines belong to the order's tenant | DB composite FK |
| Order reference unique per tenant and business day | DB unique (Q64, Q44) |
| Actor (membership or device) recorded on every transition | Svc (audit / history) |

### Order line and kitchen ticket — Proposed (Q59, Q61/UX-2, Q63, UX-3, Q45, Q65)
Line preparation status: new → preparing → ready → served, or voided. The ticket status is derived from its lines: *new* if all non-voided lines are new, *ready* when all are ready, *done* when all are served or voided, otherwise *preparing*. `data-engineer` may cache it in the same transaction.

| From → To | Command | Permission | Side effects | Dep. |
|---|---|---|---|---|
| new → preparing | start (ticket or line) | `kitchen.update` | `ticket.updated` → floor | Q63 |
| preparing → ready | ready (ticket or line) | `kitchen.update` | `ticket.ready` → waiter alert | Q63, Q70 |
| preparing → new | undo start | `kitchen.update` | Only within the undo window (60 s) | Q63 |
| ready → preparing | back to preparing | `kitchen.update` | Any time before served (F5 "Back to preparing") | Q63 |
| ready → served | mark served | `orders.update` (kitchen too if UX-3 = yes) | Ticket leaves board when done | Q59, UX-3 |
| served → ready | undo served | `orders.update` | Within undo window | Q63 |
| new → voided | void before preparation | `orders.update` | `line.voided` → kitchen; audit | Q61 |
| preparing/ready → voided | void after start | `orders.cancel` + mandatory reason | `line.voided` → kitchen (struck through); audit | Q61, UX-2 |
| served → voided | — | not in v1; corrections via billing (Phase 6) | — | Q61, Q14 |

Invariants: quantity is a whole number ≥ 1 (DB CHECK). Snapshot of name, unit price, modifiers and price deltas taken when the line is added and never changed (DB NOT NULL + Svc, Q50). A sent line's quantity is immutable; reducing it is a void (whole or partial, `data-engineer` decides the shape). Every ticket belongs to one order and has ≥ 1 line (Svc). Status transitions are idempotent: repeating the current transition returns the current state (Svc). Notes ≤ 200 characters (DB CHECK, Q65).

## Domain events (for kitchen display, table view, audit, later inventory/reports)
`restaurant.created|suspended|reinstated|closed`, `invitation.created|accepted|revoked`, `membership.created|suspended|reactivated|removed|roles_changed`, `device.paired|revoked`, `menu.item_changed|availability_changed|price_changed|archived`, `table.changed|occupancy_changed`, `order.sent|closed|cancelled|moved`, `ticket.updated|ready`, `line.voided|served`. Realtime delivery through the tenant-scoped outbox (`overview.md`); channel names from the resolved tenant (TM-20).

## Open items raised here (for `requirements.md`, via requirements-analyst)
Transcribed to `requirements.md` as Q72–Q79 (change 0002, Track A2). Status after the product owner's answers (2026-09-30):
- **AQ1** (= Q72) existing user added as staff: **answered → C6.20.** A staff account cannot be created for an email or username that already belongs to a User; the manager uses a different identifier; the message never names another restaurant. Only owners join an existing identity to a restaurant, by invitation (C6.6). The architecture still allows one User in several restaurants (C2.4).
- **AQ2** (= Q73) username scope: **answered → C6.18** (unique platform-wide).
- **AQ3** (= Q74) staff email verification: **answered → C6.21.** No staff email features in v1; the staff email is contact information only; staff resets go through a manager (C6.15, C6.16).
- **AQ4** (= Q75) counter/POS tablet in v1: **answered → C6.17.** Kitchen display profile only; staff take orders and payments on their own devices; PIN switch later.
- **AQ5** (= Q76) device after removal of the pairing member: open (non-blocking).
- **AQ6** (= Q77) RS-1 wording (pending owner invitation): open (Phase 3).
- **AQ7** (= Q78) audit payloads for staff personal fields: **answered → C6.22.** Name/contact "changed" without values; roles, permissions, status and device profile with full old and new values; login identifiers as a keyed hash of old and new.
- **AQ8** (= Q79) minimization vs "history keeps the original name": open (Phase 3).
