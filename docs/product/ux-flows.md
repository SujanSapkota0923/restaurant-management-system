# UX Flows — navigation model and core flows

**Status:** Proposed (change 0002, Track B; updated for C6.11, C6.13, C6.14; synced to C6.4–C6.7 and C6.15–C6.23 in Track E). Not binding until requirements it depends on are answered. Owner: `ux-designer`. Principles: `ux-principles.md`.

Conventions on this page:
- **Taps** are counted from the role's home screen; typing is listed separately. Target for frequent operations: ≤ 3 taps (`ux-principles.md` §1).
- **Depends on Qn** = designed for the suggested default of an open question in `requirements.md`; revisit when answered.
- Permission codes are from permission catalog v1 in `architecture/authorization.md` (approved, C6.19; device eligibility and the Kitchen display profile still Proposed). UI uses them for display only; the server decides.
- Layout baseline 360×640, one hand, thumb zone = bottom third. Targets ≥ 44×44 px on phone, ≥ 64×64 px on kitchen display.

## 1. Navigation model

### 1.1 App shell (phone)
- **Top bar (always visible):** restaurant name (switcher trigger when the user has more than one active membership), connection indicator, account button. The restaurant name is never hidden: the user must always know which tenant they are acting in.
- **Bottom tab bar:** up to 4 destinations + **More**. Tabs are derived from effective permissions, never role names (legacy did `role === 'admin'` routing, `../rms/frontend/src/pages/Login.jsx:19,63` — avoid).

| Priority | Tab | Shown when user has |
|---|---|---|
| 1 | Tables | `tables.view` |
| 2 | Orders | `orders.view` |
| 3 | Kitchen | `kitchen.view` |
| 4 | Dashboard | `dashboard.view` |
| — | More (Menu, Staff, Devices, Reports, Settings, Account, Sign out) | always (items filtered by permission) |

- The first 4 permitted tabs are shown in priority order; the rest move into More. A user with a single destination gets no tab bar.
- **Home tab** = last-used tab for this membership (non-sensitive UI preference), else the first permitted tab. ASSUMPTION: owners learn to land on Dashboard after one use; waiters land on Tables.
- **Quick edits** use bottom sheets over the current screen; full-screen navigation only for lists/detail. Back always returns to the previous context with state kept.
- **Permission changes mid-session** (revocation is immediate, ADR-0006/`authorization.md`): the next 403 shows the permission-denied state (§3) on that screen and the shell refreshes tabs from the session endpoint.

### 1.2 Restaurant switcher
Top-bar restaurant name → **Switch restaurant** sheet. Not in the bottom bar: switching is rare, but the current restaurant must be visible everywhere. Hidden (name not tappable) for single-membership users. Flow F2.

### 1.3 Kitchen display mode — Depends on Q13; Kitchen display profile Proposed (not covered by the C6.19 approval)
- Full-screen, landscape tablet or wall screen; no bottom bar, no top-bar menus. Only the restaurant name, device name, connection state and clock.
- **Default:** a *device session* (C6.4) with the Kitchen display profile; actions are attributed to the device (C6.13). Pairing and revoking are done by a member with `devices.manage` using a single-use pairing code (C6.14, security DV-02) — flow F7. No personal password is ever typed on the tablet.
- **Fallback:** a personal session with `kitchen.view` opens the Kitchen tab and can tap **Full-screen display** (same board, shell hidden).
- Screen wake lock while open; new-ticket chime plays on the device (volume on device, not in app settings).

### 1.4 Global states (every screen)
- **Offline/slow:** a banner under the top bar ("No connection — changes not sent yet") plus a per-item pending marker on anything waiting. No full offline mode (C6.7): nothing is queued silently; unsent work stays on screen with **Retry**.
- **Session expired:** re-auth sheet over the current screen; unsent drafts in memory are kept and resent after sign-in.
- **Success:** brief toast at the bottom, above the tab bar, never blocking; with **Undo** when the action is reversible.

## 2. Confirmation rules applied
| Action | Reversible? | Pattern |
|---|---|---|
| Add/remove draft line, change qty, switch restaurant, ticket status change, mark served | Yes | Act + undo toast (or undo by the inverse control) |
| Send to kitchen | Not undoable once cooking starts; not money | No confirm (routine); draft is visible on the send bar before sending; later removal = cancel/void rule (open question UX-2) |
| Close order | No; money-affecting once billing exists | Confirm stating total, item count and "can't be edited after closing" |
| Cancel order / void sent line | No; money + audit (`orders.cancel`) | Confirm with consequence; reason field per business rule (UX-2) |
| Add staff / change role to a role with high-risk permissions (`staff.manage`, `roles.manage`, `devices.manage`, `billing.refund`, `settings.manage`), or invite an owner | Revocable, but grants power immediately | Confirm naming the powers granted (REVIEW) |
| Reset a staff password | No; ends their sessions, audited (C6.15, SP-05/06); clears the PIN once PIN switch exists (C6.17) | Confirm stating those consequences |
| Revoke a shared device | No; display goes dark until re-paired | Confirm naming the device and the effect |
| Leave the temporary-password hand-over screen | Recoverable only by a new reset | No dialog; the screen states "You won't see this again" above **Done** |
| Discard unsent draft (sign out, switch restaurant) | No | Confirm naming what is lost |

## 3. Standard states
Every flow below uses these unless it states otherwise.
- **Loading:** skeleton of the target layout; the top bar and tab bar stay interactive. Buttons that submit show an inline spinner and are disabled (no double submit); inputs are never cleared.
- **Empty:** one sentence of why + the next action (or who can do it).
- **Error:** what failed, what to do, input kept; field errors next to the field.
- **Permission-denied:** "You don't have permission to <do X> at <restaurant>. Ask an owner or manager." No hidden-button-only treatment for actions users reach by link or stale screen.

## 4. Core flows

### F1. Sign in (incl. multi-restaurant user) — per C6.4, C6.5
Goal: get to work in the right restaurant. Role: anyone. Device: phone (also tablet). Frequency: once per shift or less.

1. **Sign-in** screen: identifier field (email or username, C6.4) autofocused, password with labelled show/hide toggle, **Sign in** at bottom. Typing: identifier + password. **Taps: 1.**
2. If MFA enabled for the account (optional TOTP for owners, C6.5): **Code** screen, numeric keypad, auto-submit on 6th digit. **Taps: 0.**
3. Membership resolution:
   - one active membership → home tab. **Total taps: 1.**
   - several, and last-used is still active → enter it; restaurant name in top bar and toast "Signed in to <name> · Switch". **Total: 1.** (REVIEW: alternative is always showing the chooser, +1 tap.)
   - several, no last-used → **Choose restaurant** screen: list of active memberships (name, your role name as label). Tap one. **Total: 2.**
States:
- Wrong credentials: "Email or password is incorrect" (no hint which), identifier kept, password cleared, focus on password. Legacy kept errors inline (`Login.jsx:118`) — keep.
- Too many attempts: "Too many attempts. Try again in N minutes." with no form wipe.
- Email not verified (owners, C2.6, C6.11): **Verify email** screen with **Resend** (cooldown shown) and "Use a different account". Staff emails are never verified in v1 and this screen never appears for staff (C6.21).
- Offline/slow: "Can't reach RMS. Check your connection and try again." — distinct from bad credentials (legacy did this, `Login.jsx:70` — keep).
- Temporary password (C6.11, C6.15): after sign-in the user lands on **Set new password** instead of home (F3 step 8).
- No active memberships: "You're not a member of any restaurant yet. Ask your manager to add you." + **Sign out**. Suspended memberships are listed disabled with "Access suspended — contact <restaurant>" (ASSUMPTION, UX-4).
- Success: lands directly on home; no success toast needed.
Accessibility: 16px inputs (legacy `text-sm` inputs, `Login.jsx:136` trigger iOS zoom — avoid); icon toggle labelled "Show password" (legacy unlabelled, `Login.jsx:155-161` — avoid); no pointer-driven decorative motion (`Login.jsx:24-43` — avoid).

### F2. Switch restaurant
Goal: act in another restaurant. Role: multi-membership user (often an owner). Device: phone.
1. Tap restaurant name in top bar → **Switch restaurant** sheet (current one ticked, others listed). **Taps: 1.**
2. Tap target restaurant. **Taps: 2.** Server sets the active membership and rotates the session (ADR-0006).
3. All cached data of the previous restaurant is dropped before rendering; skeleton of the new home tab; top bar shows the new name immediately with a pending marker until confirmed.
States:
- Unsent draft exists: confirm "You have 3 unsent items for Table 5 at <A>. Switching discards them." [Stay] [Discard and switch].
- Error/offline: sheet stays open, "Couldn't switch. You're still in <A>." Nothing changes.
- Permission-denied (membership suspended since list loaded): row shows "Access suspended — contact <B>"; user stays in A.
- Success: toast "Now in <B>". No undo needed: switching back is the same 2 taps.
- Empty: not reachable (switcher hidden with one membership).

### F3. Add staff member and assign role — per C6.15, C6.16, C6.18, C6.19, C6.20, C6.21, C6.23
Goal: a new person can sign in today with the right access. Role: member with `staff.manage` (guards SP-07/SP-08, `authorization.md`). Device: manager's phone, new hire usually standing next to them. Frequency: rare.
C6.11: staff are created directly with a temporary password, no email invite. C6.15: system-generated temporary password, shown once, forced change at first sign-in, expires unused after 72 h, manager can reset but never view (SP-01..SP-04). C6.20: an email or username that already belongs to any user cannot be used for a new staff account; there is no way to add an existing user as staff. C6.21: no staff email features.
1. More → **Staff** list. **Taps: 2.** Rows: name, role, status (Active / Must set password / Suspended). `staff.view` sees the list; no Add button without `staff.manage`.
2. **Add staff** (bottom, full width) → **Add staff** sheet. **Taps: 3.**
3. Typing: **Name**, **Username** (unique across the platform, C6.18), optional **Email** with hint "Optional. Contact information only." (C6.21, SP-09). Then **Role** chips (single select): only roles whose permissions the creator holds; never Owner (owners join by invitation, below). No default role: granting access is an explicit choice. "What they can do" lists the selected role's permission groups. **Taps: 4.**
4. **Create account**. **Taps: 5.** High-risk role (§2) → confirm "<name> will be able to manage staff. Create account?" (**6**).
5. **Hand-over** screen (full screen, replaces the sheet, not a toast):
   - "Give these to <name> in person." Username and temporary password in ≥ 24px monospace, grouped in 4s, no ambiguous characters (ASSUMPTION, security to confirm alphabet).
   - "Shown once. Works for 72 hours. They must choose their own password when they first sign in."
   - No copy or share button and no email option: the password must not land in chats or clipboard history (SP-04; REVIEW). Reading it out or letting them type it on their own phone is the intended hand-over.
   - The values are masked when the app goes to the background and are not kept in history, cache or storage (`no-store`); Back = Done.
6. **Done**. **Taps: 6** (7 with confirm). Above the button: "You won't see this password again. If it's lost, use Reset password." Not with them now? Tap Done and reset later when they are present; nothing is lost.
7. List shows the person as "Must set password" until first sign-in. Toast "<name> added".
8. **New staff first sign-in** (their device, F1): username + temporary password → **Set new password** screen (restricted session, SP-01): new password + confirm, rules shown inline before typing (≥ 10 characters, not a known-breached password, not the temporary one), labelled show/hide toggles, **Save and continue** → home tab. Only **Sign out** is offered besides saving.
Reset password (C6.15, C6.16, SP-05..SP-08): Staff → member → **Reset password** → confirm "Reset <name>'s password? They'll be signed out everywhere." → hand-over screen (step 5). (Once PIN switch exists, the confirm also says their PIN is cleared, PN-08; PIN is later, C6.17.) **Taps: 5**, 6 with Done. At their next sign-in: "Your password was reset by <manager> on <time>." (C6.23). Not offered on your own row (use Account → Change password) or on owners (owners use the email reset link, C6.16). For an account this restaurant did not create, or one with a membership elsewhere or an owner role anywhere, the button is replaced by "Can't reset here. Suspend access instead." with **Suspend** (C6.16, SP-07).
Change role: Staff → member → **Role** row → chips sheet → **Save** (4 taps), act + undo toast. Own row: "You can't change your own role." Owner rows editable only by owners; last owner cannot be demoted ("A restaurant needs at least one owner").
Owners (C6.6): holders of `owners.manage` see **Invite an owner** under the list → email + confirm naming full control → email invitation. Pending owner invitations are listed in their own "Owner invitations" section with **Resend** / **Revoke**; staff rows never have an invited state. Invitee: link → set password and verify email (C2.6) or sign in → lands in the restaurant. Expired/revoked link: "This invitation is no longer valid. Ask <restaurant> for a new one."
States:
- Loading: list skeleton rows. Empty: "Only you so far. Add your first staff member." with **Add staff**.
- Errors (field-level, input kept): "This username can't be used. Choose another." (same text whatever the reason, including an existing user, C6.20, SP-10); invalid email; email already belonging to a user → "This email can't be used here. Leave it empty or use another." (never names another restaurant, C6.20, SP-10); role no longer exists → chips refresh; rate limit → "Too many new accounts just now. Try again in N minutes."
- Offline: "No connection — account not created." Create re-enabled, input kept, retry reuses the idempotency key. If the account was created but the response was lost, retry shows "<name> was added, but the password can't be shown again. Reset password to get a new one." with **Reset password**.
- Set new password errors: rule not met → next to the field, input kept; temporary password expired → "This temporary password has expired. Ask your manager to reset it."
- Permission-denied: "Only people who can manage staff can add staff. Ask an owner or manager." (also on a server 403 after revocation; the hand-over screen is never shown on failure).
Legacy: avoid sending staff names to a third-party avatar service (`../rms/frontend/src/pages/Staff.jsx:102`) and whole-card click targets mixed with inner buttons (`Staff.jsx:94-109`).

### F4. Take a table order — Depends on Q10, Q12, Q13; network per C6.7
Goal: get what the guest asked for to the kitchen correctly, fast. Role: waiter (`orders.create`). Device: phone, one hand, standing. Frequency: dozens per shift.
Home: **Tables** tab — tiles grouped by area chips; each tile: table name, status by colour **and** text/icon (Free, Occupied, Ready to serve), open-order count, ready-item badge.
1. Tap table tile. **Taps: 1.**
   - No open order → **Order** screen with an empty draft.
   - Exactly one open order → that order's **Order** screen; "Start separate order" link in its header (Q12).
   - Several open orders (Q12) → **Table** sheet: orders listed (label, items, age) + **New order**. **+1 tap.**
2. **Order** screen: header = table + order label (context always visible); category chips (horizontal scroll) + search; item rows (name, price, "Unavailable" text when unavailable). Bottom **send bar**: "3 new · Rs 1,250 · Send to kitchen".
3. Tap item row. **Taps: 2.**
   - No required modifiers → added ×1 at once; the row turns into a 44px stepper (− qty +). Undo = −.
   - Has modifiers → **Item** sheet: required groups first (radio chips, menu-defined defaults preselected), optional groups (checkbox chips), qty stepper, collapsed "Add note", bottom button "Add · Rs 450" disabled until required groups are filled. **+1–3 taps.**
4. **Send to kitchen** on the send bar. **Taps: 3** for plain items. Order and lines are created in one transaction; each send becomes one kitchen ticket.
5. Success: toast "Sent to kitchen · 3 items"; draft clears; sent lines appear in the order with status chips (New/Preparing/Ready/Served).
Review/edit before sending: tap the send bar summary → **Order** sheet expands draft lines (edit qty/modifiers, swipe **or** a visible Remove button, with undo) and sent lines (read-only, status).
States:
- Loading: tile skeletons; menu skeleton rows while the draft header is already usable.
- Empty: no tables → "No tables set up. Someone with table management can add them in More → Settings."; no menu → same pattern for Menu; search with no hits → "No items match '<q>'" + clear.
- Error on send: nothing is partially sent. Line-level problems are marked on the line ("No longer available — remove or replace"; "Price changed to Rs 480") with other lines kept; user fixes and re-sends.
- Slow: send bar shows "Sending…"; after ~5 s "Still sending — don't close the app". Offline/failed: "Not sent — no connection. Retry"; draft kept; retry reuses the same idempotency key so the kitchen never gets duplicates (legacy did this, `../rms/frontend/src/pages/POS.jsx:101` — keep).
- Concurrent change (someone else added to/closed the order): additions still send if the order is open; if closed → "This order was closed by <name>. Start a new order for Table 5?" with draft kept.
- Permission-denied: with `orders.view` only, Order screen is read-only; no send bar; note "You can view orders but not take them."
Legacy: keep bottom cart bar with total (`POS.jsx:211-235`) and stepper-after-add (`POS.jsx:189-199`); avoid 32px/24px steppers (`POS.jsx:191,193`; `Orders.jsx:569-577`), `alert()` feedback (`POS.jsx:116,118`), table picked from a header `<select>` (`POS.jsx:145-162`), unconfirmed un-undoable "Clear" of the whole cart (`POS.jsx:219-225`), and no modifier support.

### F5. Kitchen ticket handling (New → Preparing → Ready) — Depends on Q13; device session per C6.4
Goal: never miss a ticket; cook in the right order; tell the floor when food is ready. Role: cook (`kitchen.view`, `kitchen.update`). Device: kitchen tablet/wall screen (landscape), wet or gloved hands; phone fallback. Frequency: constant.
Board: columns **New | Preparing | Ready** with counts (≥ 768px); on phone, a 3-segment switch with counts. Oldest first. Ticket card: table + order label (≥ 32px), age since sent ("12 min"), items with qty (≥ 24px), modifiers and notes highlighted with icon + text, status by colour **and** label.
1. New ticket arrives: card enters New with a "NEW" label, chime, highlight until started (reduced motion: no animation, highlight only).
2. Tap **Start** on the card (full-width, ≥ 64px). **Taps: 1.** Card moves to Preparing. Toast "Table 5 → Preparing · Undo".
3. Optional per-item (Q13 default): tap an item line to mark it ready (check icon + strike). Last item ready → ticket moves to Ready.
4. Tap **Ready** on the card. **Taps: 1.** Card moves to Ready; floor sees it (F6). Toast with **Undo** (large, 10 s).
5. Ready cards stay until marked served (F6), then leave the board. Ready cards have a **Back to preparing** button (no small menus).
States:
- Loading: column skeletons. Empty: "No tickets. New orders appear here automatically." plus connection state.
- Offline: full-width red banner "Offline — new tickets may be missing. Reconnecting…" + "last updated 14:32". On reconnect the board fully resyncs by ticket id (no missing, no duplicates). Taps while offline show the card as pending (hatched + "Saving…"); on failure it returns to its column with "Couldn't update — try again".
- Conflict: two cooks tap the same ticket → transition is idempotent; the loser just sees the current state.
- Cancelled line after sending: shown struck through with a "CANCELLED" label in red + icon; stays visible until the ticket leaves the board.
- Permission-denied / device revoked: full-screen "This display was disconnected. Ask a manager to pair it again." with **Enter pairing code** (F7). No stale board left visible.
Legacy: keep optimistic status change with rollback and version check (`../rms/frontend/src/pages/Orders.jsx:201-229`) and highlighted kitchen note (`Orders.jsx:449-453`); avoid `alert()` on failure (`Orders.jsx:228`), small `py-2` buttons, hover-dependent styling, and one-tap Cancel with no confirm next to Start/Ready (`Orders.jsx:399,421`).

### F6. Mark served / close order — Depends on Q12, Q14
Goal: get ready food to the guest and finish the order. Role: waiter (`orders.update`). Device: phone.
1. Table tile shows "Ready (2)" badge; Orders tab badge counts ready tickets. Tap the table. **Taps: 1.**
2. Order screen shows ready lines at the top with **Mark served** per ticket. **Taps: 2.** Toast "Served · Undo".
3. **Close order** (visible when all lines are served or cancelled). **Taps: 3.** Confirm: "Close Table 5's order? 6 items, Rs 2,340. It can't be edited after closing." [Keep open] [Close order] (**4**).
4. When the table's last open order closes, the tile returns to Free.
States:
- Close blocked: button disabled with the reason ("2 items still preparing").
- Error/offline: order stays open, "Couldn't close — no connection. Retry." Undo of served follows F5 offline rules.
- Permission-denied: without `orders.update`, ready lines show status only.
- Dependency: once billing exists (Q14, Phase 6), closing is expected to follow taking payment (`billing.take_payment`); this step will be redesigned then. Legacy pointed to Billing from the ready state (`Orders.jsx:428-432`).

### F7. Pair a shared device — Kitchen display profile Proposed; depends on Q82 (rotation/stale devices)
Goal: a kitchen tablet shows tickets without anyone's password on it. Role: member with `devices.manage` (C6.14) on their own phone + the tablet. Frequency: rare (setup, replacement).
1. Tablet: open RMS → sign-in screen → **Set up as shared display** (secondary link below Sign in) → **Enter pairing code** screen: one large code field, device keyboard. **Taps (tablet): 1.**
2. Phone: More → **Devices**. **Taps: 2.** Rows: device name, profile, paired by, last seen, status (Active / Not seen for N days).
3. **Pair device** (bottom, full width) → sheet: **Name** prefilled "Kitchen display <n>" (editable), **Profile** chips with the permitted profiles only (v1: Kitchen display, preselected when it is the only one) and "What it can do". **Taps: 3.**
4. **Get pairing code**. **Taps: 4.** Sheet shows the code in ≥ 32px grouped characters, "Single use · expires in 9:58" countdown, **Cancel code**.
5. Tablet: type the code → **Pair**. **Taps (tablet): 2.** Tablet opens the kitchen board (F5) with the device name in its top bar.
6. Phone sheet updates to "Kitchen display 2 is paired" and closes; the row appears in the list. Toast. No undo: revoke is the inverse.
Revoke: Devices → device row → **Revoke** → confirm "Revoke Kitchen display 2? It stops showing tickets now. You'll need a new pairing code to use it again." [Keep] [Revoke]. **Taps: 5.** The tablet shows F5's disconnected state on its next request.
States:
- Loading: list skeleton; the code area shows a skeleton until the code arrives. Empty: "No shared devices. Pair a kitchen display so cooks see tickets without signing in."
- Tablet errors: wrong, used or expired code all show "This code isn't valid. Get a new code on the manager's phone." (one message, no oracle); rate limit → "Too many tries. Wait N minutes." Input cleared, focus kept.
- Code expired on the phone: countdown ends → "Code expired" + **Get new code** (1 tap).
- Pairer lost `devices.manage` before the tablet redeemed it: tablet gets the invalid-code message; phone shows permission-denied.
- Offline: tablet "Can't reach RMS. Check the Wi-Fi and try again." (code kept); phone "No connection — no code issued", **Get pairing code** re-enabled.
- Permission-denied: "Only people who can manage devices can pair or revoke them. Ask an owner or manager." Without `devices.manage` the Devices item is hidden.
- Credential rotation (DV-04) is invisible on the tablet; no state to design.
Accessibility: code field labelled "Pairing code", large targets on the tablet (≥ 64px), countdown announced at 1 minute left, not every second.

### F8. PIN switch-in on a counter tablet — Planned (later, C6.4, C6.17); PIN rules Q81
Not designed yet, not in v1. C6.13 requires orders and payments taken on a counter/POS tablet to be attributed to a person. C6.17: v1 has no counter/POS device profile; staff take orders and payments with F4 on their own logged-in device. When PIN switch is built, the flow must follow PN-01..PN-11: tap your name tile, then a ≥ 6-digit PIN on an on-screen keypad (no PIN-only lookup), the switched-in name always visible in the top bar with a **Lock** button, auto switch-out after inactivity (suggested 90 s), and a 403 `individual_required` opening the switch-in sheet with the draft kept. Target: switch-in ≤ 2 taps + PIN.

## 5. Accessibility checklist (all flows)
Targets ≥ 44px (kitchen ≥ 64px) with ≥ 8px spacing · body text ≥ 16px, supports 200% text scaling · WCAG 2.2 AA contrast; status never by colour alone · every icon button labelled · sheets/dialogs trap focus, return focus to the trigger, close on Escape/back · toasts announced via polite live region; errors via assertive · swipe actions always have a visible button equivalent · no hover-only affordances · reduced motion respected.

## 6. Open questions raised (for `requirements.md` via requirements-analyst)
- UX-1 (non-blocking): Enter last-used restaurant directly after sign-in, or always show the chooser?
- UX-2 (blocking Phase 5): Who may remove/void a line after it is sent, is a reason required, and does it depend on kitchen status?
- UX-3 (non-blocking): May kitchen mark tickets served, or only floor staff?
- UX-4 (non-blocking): Should suspended memberships be visible to the user in the chooser?
- UX-5: answered 2026-09-30 — `devices.manage` (C6.14).
- UX-6 (non-blocking): Should an unsent draft survive an app restart (local, non-personal)?

## 7. Suggestions (not requirements)
- "Recent" / "Popular today" chip first in the menu to cut search.
- Late-ticket highlight when age exceeds a restaurant-set threshold.
- Kitchen acknowledgement tap for cancelled lines.
- Repeat last round ("Same again") for drinks.
- Print a one-time hand-over slip for the temporary password (only if the owner prefers paper; would need security review).
