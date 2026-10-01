# Brief 02 — Restaurant setup and staff

**Status:** Draft (change 0002, Track A). Binding only where it cites a Confirmed rule (`../requirements.md`). "Pending Qn" = depends on an open question. Legacy notes are evidence, not requirements; legacy paths are relative to `../rms/`.

**Answers confirmed by the product owner (2026-09-30), recorded as C6 in `../requirements.md`:** Q1 Nepal first (NPR, Asia/Kathmandu), multi-currency-ready; Q2 operator creates tenant + owner invite; Q4 one tenant = one location; Q6/Q7 personal email/username login, device sessions for shared tablets; Q21 English only, i18n-ready.

**Updated 2026-09-30 for C6.11:** staff are created directly by a manager/admin with an initial password; there is no staff email invite and no "invited" staff status. Owners still join by invitation (C6.6). Follow-ups: Q71, Q72, Q73, Q77, Q79, Q80 in `../requirements.md`.

**Updated 2026-09-30 for C6.15–C6.23 (change 0002, Track E):** temporary staff passwords (C6.15), manager reset scope (C6.16), platform-wide usernames (C6.18), catalog and default roles (C6.19), existing users cannot be added as staff (C6.20), no staff email features (C6.21) and audit of staff personal data (C6.22) are confirmed; the text below cites them instead of "pending".

## Goal
A new restaurant goes from "account created" to "staff taking orders" in one sitting, and the owner stays in control of who can do what (C2.1–C2.3, C2.5) with every sensitive change traceable (C5).

## Actors and operating context
| Actor | Device | Frequency / pressure |
|-------|--------|----------------------|
| Platform operator | Laptop | Per new customer: creates the restaurant and invites the owner (Q2) |
| Owner | Phone first, laptop sometimes | Setup once; staff changes weekly; settings rarely |
| Manager (delegated) | Phone | Adds/suspends staff when people join or leave; sometimes during service |
| Staff | Phone | Sees own profile and role only |

Time pressure is low except "new hire starts in 10 minutes" and "fired employee must lose access now".

## Happy paths
1. **Tenant onboarding** (Q2; required details pending Q36): platform operator creates the restaurant (one location, Q4) with required details → owner invited (brief 01) → owner opens a short setup checklist (restaurant details, tax/service settings, menu, tables, staff) — each step skippable and resumable.
2. **Restaurant settings**: owner edits details (name, address, contact, logo, timezone, currency, tax/service charge — currency NPR first, multi-currency-ready per C6.1; tax/service rules pending Q15) → sees what changed → saved; change is audited.
3. **Add staff** (C6.11): Staff → Add → name, username (unique platform-wide, C6.18) and/or email (contact information only, C6.21), role(s) → Create → the system generates a temporary password and shows it once (C6.15) → staff appears as "Active" → manager gives the password to the person, who signs in and must change it at first sign-in (C6.15). No email is sent. If the email or username already belongs to an existing user, the account is not created and the manager must use a different identifier (C6.20).
4. **Change a person's access**: open staff member → change role → confirm dialog states what they gain/lose → effective on their next action.
5. **Suspend / remove**: open staff member → Suspend (reversible) or Remove → confirm → access ends immediately (C2.3).
6. **Roles**: Roles → pick a predefined role (Owner, Manager, Waiter, Cashier, Kitchen; C6.19) or "New role" → toggle permissions by group (permission groups, C2.5) with plain-language descriptions → save.

## Acceptance criteria
Tenant and settings
- RS-1 Creating a restaurant creates exactly one tenant and exactly one pending owner invitation in a single step (C1, C2.1, C6.6). The owner membership is created, active, when the invitation is accepted (reading of C2.1 pending Q77). Partial creation (tenant without owner invitation, or invitation without tenant) never persists (C4 data integrity). Test: make invitation creation fail → no restaurant exists and the operator sees an error.
- RS-2 Required restaurant details at creation are pending Q36; missing required details block creation with a field-level message.
- RS-3 Every settings change records who, when, restaurant, previous value, new value (C5). Test: change tax rate → audit event shows old and new rate.
- RS-4 Settings that affect money (tax, service charge, currency — Q15, Q1) show a confirmation stating that the change applies to new orders only and not to existing ones (pending Q50 snapshot rule; legacy snapshotted tax at order creation, `backend/apps/order/tests.py:442-459`).
- RS-5 Only members with the settings-management permission can change settings; others see settings read-only or not at all (permission-denied state per ux-principles §6). Which settings are owner-only is pending Q37.

Staff management
- RS-6 A staff member can only be created inside the current restaurant; the new membership is scoped to it (C1.1, C2.2).
- RS-7 The staff list shows each member's name, role(s) and status (active, suspended, removed — Membership lifecycle in `../../architecture/domain-model.md`) and can be filtered by status. There is no "invited" staff status: a created staff member is active immediately (C6.11). Pending owner invitations, if any, are listed separately from members, never as members. Test: create a staff member → they appear as "Active"; filter options contain no "Invited".
- RS-8 Suspending or removing a member ends their access to this restaurant on their next action (C2.3); their past actions stay attributed to them in history and audit.
- RS-9 Staff creation, role change, permission change, suspension, reactivation, removal and password reset by a manager each produce an audit event (C5, C6.15). No audit event, screen or log contains a password. Name and contact changes are recorded as "changed" without values; role, permission, status and device-profile changes record full old and new values; login identifier changes record a keyed hash of old and new (C6.22).
- RS-10 A person cannot change their own roles or permissions. Test: manager opens own profile → role controls are absent or disabled with an explanation. (Proposed guard in `../../architecture/authorization.md`; confirm via Q42.)
- RS-11 The restaurant always keeps at least one active owner; an attempt to remove/suspend/demote the last owner is refused with a message saying why (proposed guard; confirm via Q38).
- RS-12 Re-adding a previously removed person follows Q41 (open). If their user account still exists, a new staff account cannot reuse its email or username (C6.20); how Q41 interacts with C6.20 is not decided.

Roles and permissions (business view)
- RS-13 Predefined roles Manager, Waiter, Cashier and Kitchen are copied into every new restaurant as editable roles; the Owner role is not editable (C6.19). Custom roles can be created (C2.5).
- RS-14 Permissions are presented in groups with plain-language labels ("Take payments", "Change menu prices"), not codes.
- RS-15 A member can grant only permissions they themselves hold (proposed escalation guard; confirm via Q42). Attempting otherwise is refused server-side, not just hidden.
- RS-16 Editing a role shows how many people it affects before saving; the change applies to all of them on their next action.
- RS-17 Deleting a custom role that is still assigned is refused until members are moved, or offers to move them (pending Q42).
- RS-18 Direct per-member permissions (C2.5 "where justified") are visible on the member's profile as exceptions so the owner can find them (UI exposure pending Q43).
- RS-19 The owner can see, for any member, their effective permissions and who last changed them.

## Edge and failure cases
- Two managers edit the same staff member at once → the second save is refused with "changed by <name> just now — review" rather than silently overwriting (C4).
- Manager removes a staff member who is mid-order → orders stay; see brief 05 and Q40.
- Role edited during service removing a permission a waiter is using → their next action is refused with a clear reason; unsent input is not silently lost.
- Staff member belongs to two restaurants; removed from one → the other is unaffected (C2.4).
- Adding staff with an email/username that is already a member of this restaurant → "already a member", no duplicate.
- Adding staff with an email/username that belongs to a user elsewhere → the account is not created and no password is set; the manager must use a different identifier (C6.20). The "already taken" message never names another restaurant.
- New hire never signs in or forgets the temporary password → it expires unused after 72 h; a manager resets it (C6.15). Managers may reset only accounts their restaurant created that have no membership elsewhere and are not an owner anywhere; owners are never reset by managers (C6.16). Each reset is audited and ends the person's sessions (C6.15).
- Removing the member who paired a shared device → device keeps working or not per Q76 (open).
- Owner changes timezone after orders exist → historical timestamps keep their true instant; display follows the new timezone (ASSUMPTION; reporting day boundary pending Q44).
- Logo upload too large / wrong type → clear message, other fields kept.
- Double tap "Create" → one staff account.

## Must-have vs optional
- **Must-have (v1):** RS-1–RS-17, RS-19; setup checklist minimal (can be a list of links).
- **Optional / later:** RS-18 UI (Q43), branding/colour scheme, opening-hours enforcement (Q44), staff scheduling (Q18), multi-location (Q4), ownership transfer (Q38), bulk staff import.
- **Out of scope:** subscription billing (Q3).

## Legacy behavior (unconfirmed)
- Settings held payment timing (now/later), payment methods, tax rate (default 10), service charge, currency `Rs`, timezone `Asia/Kathmandu`, opening hours JSON (`backend/apps/restaurant/models.py:33-52`).
- Restaurant settings and branding were publicly readable without login (`backend/apps/restaurant/tests.py:33-56`) — unreviewed public surface.
- Admins listed only `staff` users, never other admins (`backend/apps/user/viewsets.py:26-32`); permissions were `role == "admin"` plus an `inventory_permissions` list (`backend/apps/user/permissions.py:21-65`).
- Staff on/off-shift status tied to schedules (`backend/apps/user/viewsets.py:39-62`) — see Q18.

## Open questions
Existing, answered per change 0002: Q1, Q2, Q4, Q5, Q9 (→ C6.19), Q20 (→ C6.8; which fields are minimized and how removed staff appear in history is Q79). Existing, still open: Q3 (billing), Q15 (tax rules — Nepal VAT/service charge specifics), Q18 (shifts).

New (tracked in `../requirements.md`): Q36 required restaurant details; Q37 owner-only settings; Q38 multiple owners / transfer; Q39 restaurant closure; Q40 removed staff and open work; Q41 re-hiring; Q42 who manages roles and escalation guards; Q43 direct permissions UI; Q44 opening hours and business day.

After C6.11 (tracked in `../requirements.md`): Q71 initial password rules (answered → C6.15); Q72 existing user added as staff (answered → C6.20); Q73 username scope (answered → C6.18); Q76 device after pairer removal (open); Q77 RS-1 owner invitation vs C2.1 (open); Q78 audit of personal fields (answered → C6.22); Q79 removed staff name in history (open); Q80 manager reset scope and owners (answered → C6.16).
