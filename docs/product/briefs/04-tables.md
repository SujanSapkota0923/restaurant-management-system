# Brief 04 — Tables

**Status:** Draft (change 0002, Track A). Binding only where it cites a Confirmed rule (`../requirements.md`). "Pending Qn" = depends on an open question. Legacy notes are evidence, not requirements; legacy paths are relative to `../rms/`. Q19 (tolerate brief network loss, no full offline) is answered → C6.7 in `../requirements.md`.

## Goal
Front-of-house staff see at a glance which tables are free, busy or unavailable and start or find a table's order in one tap; the owner can set up and change the floor layout without breaking order history (C4, C5 "table configuration changes").

## Actors and operating context
| Actor | Device | Frequency / pressure |
|-------|--------|----------------------|
| Owner / manager | Phone or laptop | Set up tables once; change occasionally (events, extra patio tables) |
| Host / waiter | Phone, POS tablet | Looks at the table view constantly during service; highest pressure at rush |
| Cashier | POS tablet | Opens a table to settle its bill (Phase 6) |

## Happy paths
1. **Set up**: Tables → add area (pending Q53) → add tables (name/number, seats) → tables appear in the table view.
2. **Seat a party**: table view → tap a free table → start order (brief 05); optionally enter guest count (pending Q58).
3. **Find a busy table's order**: tap an occupied table → its open order(s) open (one vs many per Q12).
4. **Take a table out of service**: manager marks table unavailable (broken, reserved for event) → staff cannot start new orders there; existing open order unaffected.
5. **Move a party** (pending Q55): open order → Move to table → pick a free table → table view updates for both tables.

## Acceptance criteria
Setup and configuration
- TB-1 A table has a name/number unique within the restaurant (scope of uniqueness — per restaurant or per area — pending Q56) and a seat count ≥ 1.
- TB-2 Creating, renaming, changing seats, moving between areas, deactivating or deleting a table records who, when, previous and new values (C5).
- TB-3 A table with any order history cannot be removed in a way that loses or alters that history (C4); a table with an open order cannot be deactivated or removed until that order is closed or moved. Legacy: `backend/apps/order/viewsets.py:118-121`.
- TB-4 Only members with table-management permission can change table configuration; everyone with table view permission can see the table view (catalog draft `tables.view`/`tables.manage`, `../../architecture/authorization.md`).

Table view (service)
- TB-5 Each table shows its name, status and — when occupied — enough to act without opening it (pending Q54 for exact fields; suggested: time since seated, order status summary). Status uses colour **and** text/icon (ux-principles §3).
- TB-6 "Occupied" is derived from the table having at least one open order; staff never set it by hand, and it clears automatically when the last open order is closed or cancelled. (Pending Q54; legacy did this, `backend/apps/order/services.py:100-110`.)
- TB-7 A manually set unavailable/closed state and the derived occupied state are shown distinctly; closing an occupied table does not hide its open order (legacy `backend/apps/order/tests.py:681-708` showed closed + occupied).
- TB-8 Table status changes made by one device appear on other devices' table views without manual refresh (latency target shared with Q63).
- TB-9 The table view is usable at 360×640 with ≥ 44 px targets, and lists ≥ 60 tables without horizontal scrolling (ASSUMPTION on 60; confirm typical size with Q57).
- TB-10 Starting an order on a table that became occupied/unavailable a moment ago (another device) is handled per Q12: either joins/offers the existing order or creates a second order — never silently creates a conflicting state.

Moving and merging (pending Q55)
- TB-11 Moving an order to another table is a single action; the order keeps its items, statuses, notes and history; both tables' statuses update together or not at all (C4). Legacy blocked moving onto a table with an active order (`backend/apps/order/services.py:268-273`).
- TB-12 Moving is recorded (who, from, to, when).

## Edge and failure cases
- Two waiters tap the same free table at the same moment → outcome per Q12; neither sees an error-free "success" for a state that did not happen.
- Table renamed while orders are open → open orders and kitchen tickets show the new name; past orders show… pending Q56 (suggested: name as of the order).
- Party of 10 on tables 4+5 (join) → pending Q55; until decided, staff use one table and note it.
- Party moves mid-meal after items are sent to the kitchen → kitchen tickets show the new table (pending Q55, Q63).
- Table marked out of service while a reservation exists → reservations are Phase 9 (Q17); flag conflict then.
- Seat count 0, negative, or absurd (500) → rejected with a message; ASSUMPTION: upper bound only as a sanity limit.
- Last table in an area deleted → area remains, shown empty with "add table" next step.
- Network lost on the table view → stale indicator ("last updated 40 s ago") and retry, never a silently stale grid (ux-principles §6, Q19).

## Must-have vs optional
- **Must-have (v1):** TB-1–TB-10.
- **Optional / later:** areas (Q53, may become must-have), TB-11/12 move (Q55), merge/split tables, visual floor plan (Q57), guest count (Q58), needs-cleaning state (Q54), customer QR per table (Q11).
- **Out of scope:** reservations logic (Phase 9, Q17).

## Legacy behavior (unconfirmed)
- Statuses `available / occupied / reserved / waiting / closed`; separate manual `operational_status` with occupied derived from active orders (`backend/apps/order/models.py:10-46`).
- One active order per table enforced by a database constraint (`backend/apps/order/models.py:116-122`) — see Q12.
- Per-table signed QR tokens with a version counter; rotating revokes printed codes, with a confirm dialog "Existing printed copies will stop working" (`backend/apps/order/viewsets.py:42-66`, `:114-116`; `frontend/src/pages/Tables.jsx:221`; tests `backend/apps/order/tests.py:511-519`) — only relevant if Q11 = yes.
- Reservations lived on tables with capacity and overlap checks (`backend/apps/order/tests.py:484-509`) — Phase 9.
- `Table → Order` cascade delete (`backend/apps/order/models.py:87`) — history-loss risk.

## Open questions
Existing: Q10 (service model — takeaway has no table), Q11 (table QR self-order), Q12 (one vs many orders per table), Q17 (reservations), Q19 (network loss, answered → C6.7).

New (tracked in `../requirements.md`): Q53 areas; Q54 table states and what the tile shows; Q55 move/merge; Q56 naming, uniqueness and deletion; Q57 layout style and typical size; Q58 guest count.
