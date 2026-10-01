# Brief 01 — Identity and access

**Status:** Draft (change 0002, Track A). Binding only where it cites a Confirmed rule (C-numbers in `../requirements.md`). Everything marked "pending Qn" depends on an open question. Legacy notes are evidence, not requirements; legacy paths are relative to `../rms/`.

**Answers confirmed by the product owner (2026-09-30), recorded as C6 in `../requirements.md`:** Q2/Q5 operator creates tenant + owner invite, no operator tenant-data access except audited break-glass; Q6/Q7 personal email/username + password on personal devices, limited device session on shared kitchen/counter tablets, PIN later; Q19 tolerate brief network loss, no full offline; Q21 English only, i18n-ready. This brief is written against those answers.

**Updated 2026-09-30 for C6.11:** staff are not invited by email; a manager creates the staff account and sets the initial password. Email invitations are used for owners only (C6.6). Staff flows and criteria below are revised accordingly; follow-ups are Q71–Q74 and Q80 in `../requirements.md`.

**Updated 2026-09-30 for C6.12, C6.15–C6.23 (change 0002, Track E):** session, password and reset rules (C6.12), temporary staff passwords (C6.15), manager reset scope (C6.16), no counter/POS device profile in v1 (C6.17), platform-wide usernames (C6.18), catalog and default roles (C6.19), existing users cannot be added as staff (C6.20), no staff email features in v1 (C6.21), audit of staff personal data (C6.22) and acceptance of R19 (C6.23) are now confirmed; the text below cites them instead of "pending".

## Goal
Every person who works in a restaurant can get into RMS quickly and safely on their own phone or on a shared restaurant device. They see only the restaurant(s) they belong to and only what they are allowed to do (C1.1, C2.3). The owner can always tell who did what (C5).

## Actors and operating context
| Actor | Device | Frequency / pressure |
|-------|--------|----------------------|
| Owner / admin | Own phone, sometimes laptop | Daily; low time pressure; sensitive actions (staff, money, settings) |
| Staff (waiter, cashier, manager) | Own phone (no shared counter/POS device in v1, C6.17) | Start of every shift; must be in within seconds; may be mid-rush |
| Kitchen | Shared, wall-mounted or counter tablet (kitchen display) | Logged in all day; nobody types a password with wet hands (device session, C6.4) |
| Invited owner who has not signed up yet | Phone, via email link | Once |
| New staff member with a manager-set initial password (C6.11) | Own phone, often in front of the manager | Once, usually minutes before their first shift |
| Platform operator | Office | Rare; creates each tenant and the owner invite (Q2) |

Network: restaurant Wi-Fi, often flaky; mobile data as fallback (Q19).

## Happy paths
1. **Owner first access** (Q2): platform operator creates the restaurant and invites the owner → owner opens the invite → sets password → verifies email → lands on their restaurant's empty dashboard.
2. **Staff account created by a manager** (C6.11): manager enters name + username (unique platform-wide, C6.18) and/or email (contact information only, C6.21) + role → the system generates a temporary password and shows it once (C6.15) → manager hands it to the staff member → staff signs in → must change the password at first sign-in (C6.15) → is inside that restaurant with that role's permissions. No email is sent. If the email or username already belongs to an existing user, the account is not created and the manager must use a different identifier (C6.20).
3. **Login**: enter email or username + password (Q6) → if one active membership, land on its home; if several, land on the last-used restaurant (pending Q32 / UX-1) with a visible switcher.
4. **Switch restaurant**: open switcher → pick restaurant → screen reloads under that restaurant; nothing from the previous restaurant remains visible.
5. **Forgot password (owners)**: enter email → receive reset link (valid 1 hour, C6.12) → set new password → all other sessions end → sign in. Owners are never reset by managers (C6.16). Staff have no email reset in v1: their password is reset by a manager (C6.15, C6.16, C6.21).
6. **Shared kitchen device** (C6.4; who may pair it: C6.14 `devices.manage`; attribution: C6.13; no counter/POS device profile in v1, C6.17): a permitted person pairs the device once → device shows only kitchen screens → stays signed in across shifts until a manager signs it out or revokes it.
7. **Sign out**: one tap from the account menu; on a shared device the next user starts clean.

## Acceptance criteria
Identity and membership
- IA-1 A user identity exists independently of any restaurant; one user may hold memberships in several restaurants (C2.4). Test: the same email invited as owner by two restaurants ends as one user with two memberships. An existing user cannot be added as *staff* (C6.20); only owner invitations add a membership to an existing user (C6.6).
- IA-2 A user with no active membership in restaurant X cannot see any X data or X's existence via any screen or request (C1.1). Legacy equivalent: `backend/apps/user/tests.py:89` (login rejected for outsider).
- IA-3 Suspending or removing a membership blocks that person's access to that restaurant on their next action, without affecting their other restaurants.

Email verification (C2.6)
- IA-4 Email addresses are verified by a single-use, time-limited link. Expired or reused links show "link expired, request a new one" and change nothing.
- IA-5 An owner cannot use the restaurant until their email is verified (C6.11, C2.6). A staff member's email is contact information only: it is not verified, receives no reset link or other account email, and grants nothing (C6.21). Whatever is blocked is enforced server-side, and the screen says what is blocked and how to fix it. Test: request a password reset for a staff member's email → no email is sent and the response is the same as for an unknown email (IA-13).
- IA-6 Accepting an owner invitation through the emailed link counts as verifying that email (C2.6, C6.6; Invitation lifecycle in `../../architecture/domain-model.md`). Test: owner accepts the invitation → their email shows as verified and no separate verification email is required. Staff are not invited (C6.11), so this criterion never applies to staff accounts.

Login and sessions
- IA-7 Wrong identifier or wrong password produce the same message; the message never reveals whether the account exists.
- IA-8 Repeated failed attempts get a progressive delay, with no permanent lockout (C6.12); the user sees when they may try again. C6.12 does not fix the delay steps.
- IA-9 Successful login, failed login, logout, password change/reset, and session revocation are recorded as security events with who, when, restaurant (if any), device description and outcome (C5).
- IA-10 A password change or reset ends every other session of that user (ADR-0006, Accepted); a manager reset ends all of the person's sessions (C6.15).
- IA-11 Personal-device sessions end after 12 h idle or 30 days absolute; shared-device sessions have no idle timeout and stay valid until revoked (C6.12). A timed-out user sees "signed out for inactivity" and returns to the same screen after signing in, with unsent input either kept or clearly reported as not saved.
- IA-12 A user can end all of their own sessions ("sign out everywhere") (pending Q35 for the session list).

Password reset
- IA-13 Requesting a reset for an unknown email shows the same confirmation as for a known email.
- IA-14 Reset links are single-use and valid for 1 hour (C6.12); using one after a newer link was issued fails. In v1 reset links go only to owners (C6.16, C6.21).
- IA-15 Staff can change their own password (C6.12; legacy gap: `backend/apps/user/viewsets.py:64-77` limited it to admins).

Restaurant switching
- IA-16 Each session acts in exactly one restaurant at a time; the current restaurant name is always visible on screen.
- IA-17 After switching, lists, counts, notifications and cached screens show only the new restaurant's data. Test: switch A→B, press back; no A data is shown.
- IA-18 Switching is recorded (security event) and does not require re-entering the password. MFA is optional TOTP for owners and mandatory for platform operators (C6.5); whether switching asks an MFA-protected owner for a code is not decided.

Shared devices (C6.4, C6.13, C6.14, C6.17)
- IA-19 A device session can only use the permissions granted to that device (e.g. kitchen view/update), never the permissions of the person who paired it.
- IA-20 A person with `devices.manage` (C6.14) can see all signed-in shared devices for the restaurant and revoke any of them; revocation takes effect on the device's next action.
- IA-21 Every action on a shared kitchen display is attributed in the audit record to the device (C6.13). Orders and payments are never taken on a shared device in v1: there is no counter/POS device profile (C6.17), so they are always attributed to the signed-in individual.

Staff accounts with a manager-set password (C6.11)
- IA-22 A staff member can sign in with the system-generated temporary password shown once to their manager, and no invitation email is sent (C6.15). They must replace it at first sign-in before doing anything else; an unused temporary password expires after 72 h; managers can reset it but never view it (C6.15). At sign-in after a manager set or reset the password, the staff member sees a notice (C6.23). The temporary password never appears in any screen after creation, in audit records or in logs. Test: create staff, inspect the audit event and the staff profile → no password or password hint is visible.

## Edge and failure cases
- Same email used in two restaurants (owner invitation or staff account) with different capitalisation → treated as the same email (case-insensitive match). ASSUMPTION: needs confirmation only if the platform supports case-sensitive local parts; suggested no.
- Owner invitation sent to an email that already has an account → accepting adds a membership; no second account; the existing password is kept.
- Manager creates a staff account with an email or username that already belongs to a user (e.g. staff at another restaurant) → the account is not created, no password is set or changed, and the manager must use a different identifier (C6.20). The "already taken" message never names another restaurant.
- Owner invitation accepted after the inviting operator/owner was removed → invitation still valid only if it has not been revoked or expired (Q28, open).
- New staff member never signs in / forgets the temporary password → it expires unused after 72 h and a manager resets it (C6.15), within the reset scope of C6.16 (only accounts this restaurant created, with no membership elsewhere and not an owner anywhere).
- Staff member removed while signed in mid-order → their next action is refused with "Your access to <restaurant> has ended"; any unsent order input stays on screen but cannot be sent (see brief 05).
- User's only membership is suspended → after login they see "You don't have access to any restaurant" with who to contact, not an empty app.
- Shift change at the counter: v1 has no counter/POS device profile (C6.17), so each waiter takes orders and payments on their own signed-in device and is individually attributed (C6.13). PIN switch on a shared counter tablet is later (C6.4, C6.17; rules Q81).
- Suspended memberships: whether the user still sees them (disabled) in the restaurant chooser is UX-4.
- Kitchen tablet reboots / loses Wi-Fi → it resumes in the same device session when network returns, with no manual re-login; device sessions have no idle timeout and stay valid until revoked (C6.12).
- Stolen staff phone → a manager reset ends all of that person's sessions (C6.15, within C6.16 scope); a general "end sessions" action for managers without a reset is Q31 (open).
- Owner loses access to their email → recovery path pending Q34; never self-service without identity proof.
- Double tap on "Sign in" or "Send reset link" → one session / one email.

## Must-have vs optional
- **Must-have (v1):** IA-1–IA-17, IA-19–IA-20, IA-22; throttling; security event logging; own password change; MFA per C6.5 (optional TOTP for owners, mandatory for platform operators).
- **Optional / later:** PIN quick-switch (C6.4, C6.17), active-session list with device names (Q35), passwordless login.
- **Out of scope:** social login; customer accounts (Q11).

## Legacy behavior (unconfirmed)
- One user belonged to one restaurant via `User.restaurant`, role `admin`/`staff` (`backend/apps/user/models.py:14-26`). Rejected by C2.4.
- Login was per tenant hostname; outsiders rejected (`backend/apps/user/tests.py:89-100`).
- Admin set staff passwords directly at creation and reset (`backend/apps/user/tests.py:102-120`, `:236-247`); no email verification, no reset flow (`../../legacy/reference-assessment.md`).
- Access was restricted to scheduled shift hours for non-admins (`backend/apps/user/models.py:57-87`) — see Q18.
- Password change revoked existing tokens (`backend/apps/user/tests.py:221-222`).

## Open questions
Existing, answered per change 0002: Q2, Q5, Q6, Q7, Q8 (→ C6.5), Q19, Q20 (→ C6.8), Q21. Existing, still open: Q18 (shift-limited access). From `../ux-flows.md`: UX-1 (same as Q32), UX-4; UX-5 answered (→ C6.14).

New (tracked in `../requirements.md`): Q26 invite vs admin-set password (answered → C6.11); Q27 unverified-user limits (answered → C6.11); Q28 owner-invitation expiry/revocation; Q29 session timeouts (answered → C6.12); Q30 password and throttling policy (answered → C6.12); Q31 manager-initiated reset/sign-out (reset scope refined by C6.16); Q32 default restaurant after login; Q33 attribution on shared devices (answered → C6.13); Q34 owner account recovery; Q35 session list.

After C6.11 (tracked in `../requirements.md`): Q71 initial password rules (answered → C6.15); Q72 existing user added as staff (answered → C6.20); Q73 username scope (answered → C6.18); Q74 staff email verification (answered → C6.21); Q75 counter tablet before PIN switch (answered → C6.17); Q80 manager reset scope and owners (answered → C6.16); Q81 PIN rules (open); Q83 residual risk of manager-known passwords (answered → C6.23).
