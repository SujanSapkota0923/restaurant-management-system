# Product Requirements

**Status:** Draft — Phase 1 (Discovery) will expand each area. Only the "Confirmed" sections are binding. Everything else is an open question until the product owner answers it.

## Product in one paragraph

RMS is a B2B, multi-tenant restaurant management platform. The business sells RMS access to restaurants. Each restaurant is a tenant with an owner/admin account. The admin creates staff accounts and assigns permissions; staff see and do only what they are permitted. The product is mobile-first and should feel like a modern mobile app.

## Confirmed (from the bootstrap brief, 2026-09-30)

### C1. Tenancy
- C1.1 Each restaurant is a tenant. One restaurant's data is never accessible to another restaurant, whatever IDs, requests or UI bypasses are attempted.
- C1.2 Isolation is enforced server-side, including at the database level.

### C2. Accounts and access
- C2.1 An owner/admin account is created for each restaurant.
- C2.2 The restaurant admin creates staff accounts and assigns permissions.
- C2.3 Staff access only permitted functionality.
- C2.4 Identity, membership and authorization are separate concepts. The architecture must not prevent one person belonging to several restaurants.
- C2.5 The authorization model supports predefined roles, custom roles, granular permissions and permission groups; direct per-member permissions where justified.
- C2.6 Email verification exists for accounts.

### C3. Product areas (scope to be detailed in Phase 1)
Authentication · Restaurant/tenant management · Staff management · Permissions · Dashboard · Tables · Menu · Orders · Kitchen · Inventory · Reservations · History · Reports (where appropriate) · Settings · Audit logging.

### C4. Product principles
Simplicity (minimum practical interactions), mobile-first, safety never traded for simplicity, predictability (users know what happened and what's next), data integrity (transactional, no partial state). Details: `ux-principles.md`.

### C5. Auditability
Business-critical operations record who, what, when, which restaurant, which resource, previous state, new state and outcome. Examples: menu price changes, menu item deactivation, order cancellation, inventory changes, permission changes, staff creation, restaurant settings changes, table configuration changes.

### C6. Phase 1 decisions (product owner, 2026-09-30, change 0002)
- C6.1 Market: Nepal first (NPR, Asia/Kathmandu); design stays multi-currency-ready. (Q1)
- C6.2 One tenant = one restaurant location; multi-branch groups may come later as a layer above tenants. (Q4)
- C6.3 Stack: Django + DRF + PostgreSQL; React + TypeScript + Vite, delivered as an installable PWA. (Q23, ADR-0004)
- C6.4 Staff log in personally (email or username + password) on personal devices; shared kitchen/counter tablets use a limited device session; PIN quick-switch is a later option. (Q6, Q7)
- C6.5 MFA: optional TOTP for owners; mandatory for platform operators. (Q8)
- C6.6 The platform operator creates each restaurant and its owner invite (no self-service signup in v1). The operator console has no access to tenant data except audited break-glass. (Q2, Q5)
- C6.7 Network loss: tolerate brief loss with visible pending state, safe idempotent retry, kitchen reconnect and catch-up. No full offline mode in v1. (Q19)
- C6.8 Retention: orders, payments and audit records kept 7 years; staff personal data minimized after membership removal. (Q20)
- C6.9 UI language: English only in v1, i18n-ready (no hard-coded user-facing strings). (Q21)
- C6.10 Legacy `../rms` was only used locally: no data migration; its committed secrets were never used outside development and are never reused. (Q24, Q25)

- C6.11 Staff accounts are created by a manager/admin who sets the initial password (no email invite required for staff). Owner accounts still require email verification (C2.6). (Q26, Q27 — owner decision; follow-up Q71)
- C6.12 Sessions: personal devices 12 h idle / 30 days absolute; shared devices no idle timeout, valid until revoked. Passwords: minimum 10 characters plus breached-password check; staff can change their own password; progressive delay after failed logins, no permanent lockout; reset link valid 1 hour. (Q29, Q30)
- C6.13 Attribution on shared devices: kitchen display actions are attributed to the device; counter/POS tablet actions that take orders or payments must be attributed to an individual (quick PIN switch). (Q33)
- C6.14 A new permission `devices.manage` (owner + manager by default) is required to pair or revoke a shared device. (UX-5; catalog change approved)

- C6.15 Temporary staff passwords are system-generated and shown once; staff must change them at first login; an unused temporary password expires after 72 h; managers can reset but never view passwords; every reset is audited and ends the person's sessions. (Q71)
- C6.16 A manager may reset only accounts their restaurant created that have no membership in any other restaurant and are not an owner anywhere. Owners are never reset by managers; they use the email reset link. (Q80)
- C6.17 No counter/POS device profile in v1 — only the kitchen display device. Staff take orders and payments on their own logged-in devices. PIN switch comes later. (Q75)
- C6.18 Usernames are unique across the whole platform. (Q73)
- C6.19 Permission catalog v1 and default role templates (Owner, Manager, Waiter, Cashier, Kitchen) approved as proposed in `docs/architecture/authorization.md`, including new codes `menu.availability` and `owners.manage` (Owner only, never grantable). Restaurants may edit every role except Owner. (Q9)
- C6.20 A staff account cannot be created for an email or username that already belongs to an existing user; the manager must use a different identifier. The "already taken" message never names another restaurant. (Owners joining several restaurants still use invitations, C6.6.) (Q72)
- C6.21 No staff email features in v1: a staff email is contact information only; staff password resets always go through a manager (C6.15, C6.16). (Q74)
- C6.22 Audit of staff personal data: name/contact changes are recorded as "changed" without values; role, permission, status and device-profile changes record full old and new values; login identifier changes record a keyed hash of old and new. (Q78)
- C6.23 The owner accepts residual risk R19 (a manager can act as a staff member until the system-generated temporary password is changed), mitigated by forced change, 72 h expiry, audit and a notice at sign-in. (Q83)
- C6.24 Staff sign in with their platform-wide username only. Email sign-in is for owners (verified email). A staff contact email is never a login identifier. (Refines C6.4 with C6.21.)
- C6.25 The v1 shared-device profile "Kitchen display" holds exactly `kitchen.view`, `kitchen.update`, `menu.view`, `menu.availability`. Staff, roles, owners, settings, devices, audit, reports, history, money and order-taking codes are never device-eligible; `orders.view` is reserved for a future PIN-switch counter profile. Kitchen staff may mark items sold out. (Device eligibility, Q48)
## Open questions

Status: `open` / `answered (date)`. Blocking = must be answered before the named phase starts.

### Business model and platform
| # | Question | Why it matters | Suggested default | Blocking for |
|---|----------|----------------|-------------------|--------------|
| Q1 | **Answered 2026-09-30 → C6.1.** Target market(s)? Legacy defaults to Nepal (Rs, Asia/Kathmandu, 10% tax). | Currency, tax/VAT rules, fiscal invoicing compliance, language | Nepal first, multi-currency-ready | Phase 2 |
| Q2 | **Answered 2026-09-30 → C6.6.** How is a restaurant onboarded — self-service signup, or created by the platform operator? | Signup flow, abuse surface, billing | Platform operator creates tenant + owner invite | Phase 3 |
| Q3 | Is subscription billing of restaurants in scope for RMS itself? | Separate platform bounded context | Out of scope for v1 | Phase 3 |
| Q4 | **Answered 2026-09-30 → C6.2.** Does a restaurant have multiple branches/locations under one account? | Tenant = brand or = location; reports across branches | One tenant = one restaurant location; multi-location later | Phase 2 |
| Q5 | **Answered 2026-09-30 → C6.6.** Is a platform-operator (support) console needed, and may operators view tenant data? | Cross-tenant access path, audit | Minimal operator console, no tenant data access without audited break-glass | Phase 2 |

### Identity and access
| # | Question | Why | Suggested default | Blocking for |
|---|----------|-----|-------------------|--------------|
| Q6 | **Answered 2026-09-30 → C6.4.** Do staff log in with email, username, phone, or PIN on a shared device? | Auth design, shared kitchen tablets | Email/password for owners; staff email or username; PIN quick-switch as later option | Phase 2 |
| Q7 | **Answered 2026-09-30 → C6.4.** Are shared devices (kitchen display, POS tablet) used with a device login rather than a personal login? | Device sessions, audit attribution | Yes — kitchen display as a device session with limited permissions | Phase 2 |
| Q8 | **Answered 2026-09-30 → C6.5.** Is MFA required for owners? | Account takeover risk | Optional TOTP for owners in v1 | Phase 2 |
| Q9 | **Answered 2026-09-30 → C6.19.** Which predefined roles ship by default (e.g. Owner, Manager, Waiter, Cashier, Kitchen)? | Permission catalog defaults | Owner, Manager, Waiter, Cashier, Kitchen | Phase 3 |

### Operations
| # | Question | Why | Suggested default | Blocking for |
|---|----------|-----|-------------------|--------------|
| Q10 | Service model: table service, counter/takeaway, delivery — which in v1? | Order model | Table service + takeaway | Phase 5 |
| Q11 | Can customers self-order by scanning a table QR (legacy has this)? | Public unauthenticated surface, abuse | Deferred to after v1 core | Phase 5 |
| Q12 | One active order per table, or multiple (separate parties / split tabs)? | Constraint, UX | Multiple orders per table allowed, grouped by table | Phase 5 |
| Q13 | Kitchen: stations (grill, bar), courses, ticket printing? | Kitchen model | Single station v1, per-item status | Phase 5 |
| Q14 | Payments: cash only, manual QR/card confirmation, or integrated provider? Split and partial payments? Tips? Refunds? | Money handling, webhooks, compliance | Record-only payments (cash, external QR/card) with split by amount; no integrated provider in v1 | Phase 6 |
| Q15 | Tax and service charge rules; inclusive vs exclusive pricing; rounding; fiscal invoice numbering requirements? | Correctness, legal compliance | Configurable exclusive tax + service charge; rounding to 2 decimals | Phase 6 |
| Q16 | Inventory depth: simple stock counts, or recipe-based consumption with lots/costing (legacy)? | Large scope difference | Simple stock items + manual adjustments v1; recipes later | Phase 8 |
| Q17 | Reservations: who creates them (staff only or customers online)? Deposits? | Public surface, payments | Staff-entered only | Phase 9 |
| Q18 | Staff scheduling/shifts (legacy has it) — in scope? Should access be limited to shift hours? | Scope, authz rule | Out of scope v1 | Phase 3 |
| Q19 | **Answered 2026-09-30 → C6.7.** Offline operation: must order taking work without network? | Architecture (sync, conflict resolution) | Tolerate brief network loss with clear pending state; no full offline mode v1 | Phase 2 |
| Q20 | **Answered 2026-09-30 → C6.8.** Data retention: how long to keep orders, audit logs, deactivated staff data? Right-to-erasure requirements? | Storage, privacy | Orders & audit 7 years; personal data minimized | Phase 2 |
| Q21 | **Answered 2026-09-30 → C6.9.** Languages required in UI? | i18n from day one or not | English + Nepali-ready (i18n framework from day one) | Phase 2 |
| Q22 | Receipt printing (thermal printers) required? | Hardware integration | Browser print / PDF v1 | Phase 6 |
| Q23 | **Answered 2026-09-30 → C6.3.** Native app store apps, or installable web app (PWA)? | Stack | PWA | Phase 2 |

### Legacy
| # | Question | Why | Suggested default | Blocking for |
|---|----------|-----|-------------------|--------------|
| Q24 | **Answered 2026-09-30 → C6.10.** Is `../rms` deployed anywhere with real restaurant data that must be migrated? | Migration scope (ADR-0002) | No migration | Phase 2 |
| Q25 | **Answered 2026-09-30 → C6.10.** Were the secret values committed in `../rms/docker-compose.yml` ever used outside local development? | Rotation needed (R5) | Assume yes; never reuse | Phase 2 |

### From Phase 1 briefs (change 0002)
Raised by `briefs/01`–`05`. "Blocking for" names the phase that cannot start without an answer; `non-blocking` = the suggested default may be used and revisited. A suggested default is not a decision.

#### Identity and access (`briefs/01-identity-access.md`)
| # | Question | Why it matters | Suggested default | Blocking for |
|---|----------|----------------|-------------------|--------------|
| Q26 | **Answered 2026-09-30 → C6.11.** Do staff join by email invite (they set their own password), or does the admin set a password for them (legacy), or both? | Staff without email; account ownership; security | Email invite by default; admin-set one-time password (must change at first login) only for username-only staff without email (Q6 allows username login) | Phase 2 |
| Q27 | **Answered 2026-09-30 → C6.11.** What may a user with an unverified email do? Does accepting an emailed invite count as verification? | C2.6 enforcement point; onboarding friction | Owner must verify before using the restaurant; invite acceptance via link = verified | Phase 2 |
| Q28 | (Owner invitations only since C6.11.) How long are invites valid; can they be resent/revoked; does resending invalidate the old link? | Stale links, security | 7 days; resend invalidates the previous link; manager can revoke | non-blocking |
| Q29 | **Answered 2026-09-30 → C6.12.** Session idle/absolute timeouts for personal devices vs shared devices? | Security vs rush-hour re-logins | Personal: 12 h idle, 30 days absolute; shared device: no idle timeout, until revoked, re-check daily | Phase 2 |
| Q30 | **Answered 2026-09-30 → C6.12.** Password rules, self-service password change for staff, failed-login throttling and reset-link lifetime? | Account takeover; legacy blocked staff from changing own password | Min 10 chars + breached-password check; staff can change own password; progressive delay, no permanent lockout; reset link 1 h | Phase 2 |
| Q31 | May a manager reset a staff member's password or force-sign-out their sessions? For owners too? | Lost/stolen phone; escalation risk | Managers with staff permission may send a reset and end sessions of non-owners; only owners for owners; audited. Refined by Q80 (reset scope, owners never admin-reset) | Phase 3 |
| Q32 | With several restaurants, which one is active after login? (Same as UX-1 in `ux-flows.md`.) | Speed; wrong-restaurant mistakes | Last used; picker if none | non-blocking |
| Q33 | **Answered 2026-09-30 → C6.13.** On a shared POS/kitchen device, must each action be attributed to an individual (PIN switch), or is the device enough? | C5 "who"; speed at the pass | Kitchen display: device attribution is enough; POS tablet taking orders/payments: individual attribution required | Phase 2 |
| Q34 | How does an owner recover access if they lose their email account? | Lock-out vs social-engineering takeover | Platform-assisted recovery with identity check; audited; no self-service | non-blocking |
| Q35 | Should users see a list of their active sessions/devices and end individual ones? | Visibility after lost device | "Sign out everywhere" in v1; session list later | non-blocking |

#### Restaurant setup and staff (`briefs/02-restaurant-setup-staff.md`)
| # | Question | Why it matters | Suggested default | Blocking for |
|---|----------|----------------|-------------------|--------------|
| Q36 | Which restaurant details are required at creation (name, address, phone, timezone, currency, tax/VAT registration no.)? | Invoices, reports, compliance (Q1, Q15) | Required: name, timezone, currency; rest optional until billing | Phase 3 |
| Q37 | Which settings may only an owner change (tax/service rates, currency, closing the restaurant, ownership)? | Money and control | Money settings: anyone with settings permission, audited; ownership and closure: owner only | Phase 3 |
| Q38 | Can a restaurant have several owners? Can ownership be transferred? Must at least one owner always remain? | Continuity; escalation guard | Several owners allowed; owners can add/demote owners; last active owner cannot be removed | Phase 3 |
| Q39 | Can an owner close/deactivate their restaurant, and what happens to its data (export, retention)? | Offboarding; Q20 | Closure via platform operator; data retained per Q20; export on request | non-blocking |
| Q40 | When staff are suspended/removed, what happens to their open orders and in-progress work? | Service continuity | Nothing moves; others with permission continue them; history keeps the original name | Phase 3 |
| Q41 | Re-hiring: does re-inviting a removed person restore their old membership/history link? | History continuity | Same user identity; new or reactivated membership with fresh roles | non-blocking |
| Q42 | Who may create/edit roles and assign them? Confirm guards: no self-change, grant only what you hold, delete-in-use role blocked. | Privilege escalation | Role editing owner-only by default; guards as in `architecture/authorization.md` | Phase 3 |
| Q43 | Should direct per-member permissions be exposed in the v1 UI? | C2.5 "where justified"; complexity | Yes, in an "exceptions" section on the member profile, audited | non-blocking |
| Q44 | Do opening hours have any effect (block orders, business-day cut-off for reports/order numbers)? | Late-night service crossing midnight | Opening hours informational; configurable business-day cut-off (e.g. 04:00) for reports | Phase 5 |

#### Menu (`briefs/03-menu.md`)
| # | Question | Why it matters | Suggested default | Blocking for |
|---|----------|----------------|-------------------|--------------|
| Q45 | Are modifiers/variants in v1 (sizes, add-ons with price, required choices)? | Order line model; kitchen ticket | Yes: modifier groups with min/max and optional price delta | Phase 4 |
| Q46 | Nested categories (legacy had parent categories)? | Navigation depth vs taps | Single level | non-blocking |
| Q47 | Scheduled availability (breakfast only, weekdays)? | Menu model | Manual sold-out only in v1 | non-blocking |
| Q48 | **Answered 2026-09-30 → C6.25 (sold-out marking; any other part of Q48 stays open).** Who may mark an item sold out/available — kitchen staff without full menu rights? Is it audited? | Mid-rush speed; new permission code (`APPROVAL`) | Separate "availability" permission held by Kitchen and Manager; audited | Phase 4 |
| Q49 | Delete vs archive: can items/categories with order history be deleted? | History integrity (C4) | Archive only once ever ordered; hard delete only if never ordered | Phase 4 |
| Q50 | Price and tax snapshot: do order lines keep the price at time of adding? Does a later-added line of the same item use the new price? Are tax/service rates fixed at order creation or at billing? | Money correctness | Each line keeps its own price at time of adding; tax/service rates fixed at bill creation (Phase 6) | Phase 5 |
| Q51 | Item attributes and validation: image, allergen/diet tags, item code, zero-price items? | Data model; legal allergen display in some markets | Optional image and free-text tags; zero price allowed (complimentary items) | non-blocking |
| Q52 | Different prices by service type (dine-in vs takeaway)? | Price model (depends Q10) | Single price | non-blocking |

#### Tables (`briefs/04-tables.md`)
| # | Question | Why it matters | Suggested default | Blocking for |
|---|----------|----------------|-------------------|--------------|
| Q53 | Areas/sections (indoor, patio, first floor)? | Table view grouping | Optional areas | non-blocking |
| Q54 | Which table states exist, which are manual vs derived, and what does a table tile show? (Legacy: available/occupied/reserved/waiting/closed.) | Glanceable service view | Derived: free/occupied; manual: out of service; reserved from Phase 9; tile shows time seated + order status | Phase 4 |
| Q55 | Can an order be moved to another table? Can tables be merged/split for large parties? | Real service workflow | Move in v1; merge later | Phase 4 |
| Q56 | Table name uniqueness scope; renaming; removing tables with history; do past orders show the old name? | History integrity | Unique per restaurant; deactivate if history exists; past orders show name as at the order | non-blocking |
| Q57 | Grid/list vs drawn floor plan? Typical and maximum tables per restaurant? | UX and performance targets | Grid grouped by area; design for up to 100 tables | non-blocking |
| Q58 | Capture guest count (covers) per order/table? | Reports, per-cover metrics | Optional field at seating | non-blocking |

#### Orders and kitchen (`briefs/05-orders-kitchen.md`)
| # | Question | Why it matters | Suggested default | Blocking for |
|---|----------|----------------|-------------------|--------------|
| Q59 | Order lifecycle: which states (e.g. draft, sent, in preparation, ready, served, closed, cancelled) and who may move between them (incl. UX-3: may kitchen mark served)? | Core model; legacy set differs | Draft → sent → in preparation → ready → served → closed; cancelled from any open state with permission | Phase 5 |
| Q60 | Adding items to a sent order: new kitchen ticket ("round") or edit of the existing one? | Kitchen confusion; legacy reset whole order to pending | New ticket per send; existing lines keep status | Phase 5 |
| Q61 | Removing/reducing sent items (void): who may, reason required, allowed once preparation started? (Same as UX-2 in `ux-flows.md`.) | Money, waste, fraud | Before preparation: order taker; after: manager permission + reason; always audited | Phase 5 |
| Q62 | Cancelling a whole order: who may, reason mandatory, allowed after items were cooked/served? | Money, fraud (C5) | Manager permission + mandatory reason; audited | Phase 5 |
| Q63 | Kitchen display: bump per line or per ticket, recall/undo window, ordering, overdue threshold, sound, max latency? | Kitchen flow (ux-principles §9) | Per-line and whole-ticket bump; undo 60 s; oldest first; overdue at 15 min; sound on new ticket; ≤ 3 s latency | Phase 5 |
| Q64 | Order reference format: short daily number to call out, and when does it reset? | Takeaway call-out; business day (Q44) | Short number resetting per business day + unique internal reference | non-blocking |
| Q65 | Notes: per order, per line, or both? Length limit? | Allergies and prep requests reach the kitchen | Both; 200 characters per note | non-blocking |
| Q66 | If an item is sold out at send time, is the whole send refused or only that line? | Rush-hour speed vs surprise | Whole send refused; sold-out line highlighted with "remove / replace" in one tap | non-blocking |
| Q67 | Takeaway orders: which customer details are required (name, phone)? | Call-out; personal data (Q20) | Name or short number only; phone optional | non-blocking |
| Q68 | Does an order have an assigned waiter? Can any permitted staff edit it (shift handover)? | Accountability vs continuity | Creator recorded; any staff with order permission may continue it; optional reassign | non-blocking |
| Q69 | Can a closed/paid order be reopened? By whom? | Corrections vs fraud (Phase 6) | No reopen; corrections via refund/adjustment in Phase 6 | Phase 5 |
| Q70 | How is the waiter told an order is ready? | Food waits at the pass | In-app alert on the order/table for the staff who sent it plus a "ready" filter | non-blocking |

### Follow-ups from Phase 1 answers
| # | Question | Why it matters | Suggested default | Blocking for |
|---|----------|----------------|-------------------|--------------|
| Q71 | **Answered 2026-09-30 → C6.15.** With admin-set staff passwords (C6.11), must staff change the password at first login, and may the admin see or reset it later? Is the temporary password system-generated and shown once, or typed by the manager? Does an unused temporary password expire? (Extended by Track C2 question 1, SP-01/SP-02.) | The admin knowing a staff password weakens audit attribution ("who did it"); a typed password is often weak or reused; an unused one lingers | Forced change at first login; system-generated and shown once (manager-typed allowed under the same password policy); expires unused after 72 h; admin can reset (never view); reset is audited and ends the staff member's sessions | Phase 2 |
| Q72 | **Answered 2026-09-30 → C6.20.** (AQ1) A manager creates a staff account with an email or username that already belongs to a user (e.g. staff at another restaurant, C2.4). How is that person added? | C6.11 lets a manager set a password; doing so for an existing identity would let one restaurant take over an account used elsewhere (R20) | The manager cannot set or change that user's password; the existing user receives an invitation and accepts it after signing in (their consent); the "already taken" answer never names the other restaurant | Phase 2 |
| Q73 | **Answered 2026-09-30 → C6.18.** (AQ2 = Track C2 question 5) Are usernames unique platform-wide or per restaurant? | Login speed vs information leak; a per-restaurant name needs a restaurant identifier at login and must never sign in to another restaurant | Platform-wide, with throttling; the "taken" message reveals no restaurant | Phase 2 |
| Q74 | **Answered 2026-09-30 → C6.21.** (AQ3) Must a staff member's email be verified before it can receive password resets or other account email? | Under C6.11 a manager types the email; an unverified or mistyped address could receive a reset link and take over the account (R22, SP-09) | Staff email optional and unverified until the staff member verifies it; resets go only to verified emails, otherwise the manager resets (Q71) | Phase 2 |
| Q75 | **Answered 2026-09-30 → C6.17.** (AQ4 = Track C2 question 3) C6.13 requires individual attribution on counter/POS tablets, but PIN switch is "later" (C6.4). In v1: (a) build PIN switch now, or (b) ship no counter-tablet device profile, so counter staff use their personal sign-in until PIN switch exists? | Decides v1 scope and whether counter tablets exist on day one; a counter tablet on a long-lived personal session is rejected by security (R17) | (b), unless counter tablets are needed from day one; v1 ships the Kitchen display profile only | Phase 2 |
| Q76 | (AQ5) Does removing the member who paired a shared device revoke that device? | Kitchen service continuity vs leftover access | No: the device belongs to the restaurant, "paired by" is kept for audit; that member's devices are flagged for review by `devices.manage` holders, not auto-revoked | non-blocking (decide before device pairing ships) |
| Q77 | (AQ6) C2.1 says an owner account is created for each restaurant. Is it enough that restaurant creation produces a pending owner invitation, with the owner membership created on acceptance (brief 02 RS-1)? What if the invitation is never accepted? | Onboarding transaction; a restaurant could exist with no owner yet | Yes, wording change only; the operator can resend or revoke the invitation (Q28); the restaurant has no members until acceptance | Phase 3 |
| Q78 | **Answered 2026-09-30 → C6.22.** (AQ7) Audit payloads for staff personal fields (name, contact details): record only "changed" instead of old/new values, so C6.8 minimization holds? | C5 asks for previous and new state; C6.8 asks to minimize personal data after removal | Name and contact details: "changed" without values. Authorization state (roles, grants, status, device profile): full old and new values. Email/username: keyed hash of old and new (security Track C2 verdict 10) | Phase 2 |
| Q79 | (AQ8) C6.8 minimizes removed staff's personal data, while Q40's default says history keeps the original name. Which wins for removed staff in order history, audit and reports? | Owner's "who did it" years later vs privacy | Keep a display name (e.g. first name + last initial) on history and audit, minimize everything else. This is a retention rule, so it needs the owner's answer | Phase 3 |
| Q80 | **Answered 2026-09-30 → C6.16.** (Track C2 question 2; refines Q31) May a manager reset only identities their restaurant created, that have no membership elsewhere and are not owners anywhere (SP-07)? Are owners never admin-reset, including by other owners via `owners.manage`, and use email reset or Q34 recovery instead (SP-08)? | Prevents one restaurant's manager taking over an account used in another restaurant (R20) and escalation against owners | Yes to both; everything else uses the person's own verified-email reset | Phase 2 |
| Q81 | (Track C2 question 4) PIN switch rules: minimum 6 digits? Disable the PIN after 10 consecutive failures until the staff member resets it after a password sign-in? Automatic switch-out after 90 s of inactivity? | Speed at the counter vs someone acting under a colleague's name | 6 digits; disable after 10 failures; auto switch-out after 90 s | Before PIN switch is built (see Q75) |
| Q82 | (Track C2 question 6) Shared devices: rotate the device credential every 24 h, invisible to staff? Flag devices not seen for 14 days, and revoke them automatically or only flag? | Devices never time out (C6.12), so a copied device credential works until noticed (R23) | Rotate every 24 h with a short grace; flag after 14 days for `devices.manage` holders, no auto-revoke | non-blocking |
| Q83 | **Answered 2026-09-30 → C6.23.** (Track C2 question 7) Do you accept the residual risk that a manager who sets or resets a password can act as that staff member until the password is changed (R19), mitigated by forced change, audit and a notice to the staff member? | C5 attribution relies on the owner accepting this gap | Accept with those mitigations | non-blocking |
