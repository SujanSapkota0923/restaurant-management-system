# Brief 05 — Orders and kitchen

**Status:** Draft (change 0002, Track A). Binding only where it cites a Confirmed rule (`../requirements.md`). "Pending Qn" = depends on an open question. Legacy notes are evidence, not requirements; legacy paths are relative to `../rms/`. Answered in `../requirements.md`: Q7 (→ C6.4) shared kitchen tablets use a limited device session, and v1 has no counter/POS device profile (C6.17); Q19 (→ C6.7) tolerate brief network loss with pending state, idempotent retry, kitchen reconnect + catch-up, no full offline mode. Payment and billing are Phase 6 (Q14, Q15) and only touched where orders depend on them.

## Goal
A waiter takes an order in a few taps, the kitchen sees it immediately and cannot miss it, everyone knows its status at a glance, and the order record is never duplicated, lost, or silently changed — even during the rush on flaky Wi-Fi (C4, ux-principles §3, §9).

## Actors and operating context
| Actor | Device | Frequency / pressure |
|-------|--------|----------------------|
| Waiter / host | Own phone or shared POS tablet | Dozens of orders per shift; one hand, standing, interrupted; seconds per order |
| Cashier (counter/takeaway, Q10) | POS tablet | Rapid takeaway orders; queue at the counter |
| Kitchen / bar | Shared kitchen display (device session, C6.4) | Always on; arm's length; wet/gloved hands; many tickets at once |
| Manager | Phone | Approves voids/cancellations (pending Q61, Q62); watches flow |

Network: restaurant Wi-Fi drops briefly and often (Q19). Staff shifts change mid-service.

## Happy paths
1. **Take an order (table service)**: table view → tap table → add items (search/category/recent, quantity stepper, optional note) → Send to kitchen → confirmation shows "Sent" with order number.
2. **Kitchen**: new ticket appears (sound/visual cue) → cook marks it (or lines) in preparation → Ready → waiter is notified (pending Q70).
3. **Add a round**: open table's order → add items → Send → kitchen receives only the new items as a new ticket (pending Q60).
4. **Serve and close**: waiter marks served (pending Q59) → bill and payment (Phase 6) close the order → table frees (brief 04 TB-6).
5. **Takeaway** (pending Q10, Q67): New takeaway → items → customer name/number → Send → kitchen ticket labelled takeaway.
6. **Correction**: remove an unsent line freely; void a sent line or cancel an order through the permitted path with reason (pending Q61, Q62).

## Acceptance criteria
Placing and editing
- OK-1 An order has at least one line; sending an empty order is refused (legacy `backend/apps/order/services.py:120-123`).
- OK-2 Each line stores quantity (whole number ≥ 1), the item's name and unit price as at the moment the line was added (pending Q50; legacy `backend/apps/order/tests.py:657-679`). Line and order totals are computed by the server; any client-supplied total is ignored (legacy `backend/apps/order/tests.py:330-345`).
- OK-3 Sending the same order twice (double tap, retry after timeout, network drop) creates exactly one order and one kitchen ticket; the retry shows the original result. Legacy idempotency: `backend/apps/order/tests.py:603-635`.
- OK-4 If two people change the same order at once, the second change is refused with "This order was just changed by <name> — review and retry"; nothing is silently overwritten (C4). Legacy version conflict: `backend/apps/order/tests.py:637-655`.
- OK-5 A line whose item became sold out before sending is refused with the item named; what happens to the rest of the order is pending Q66. Input is never discarded.
- OK-6 Adding items to a sent order reaches the kitchen as a distinguishable addition; lines already in preparation keep their status (pending Q60; legacy instead reset the whole order to pending, `backend/apps/order/tests.py:175-194`, `:228-240`).
- OK-7 Removing or reducing a line after it was sent follows Q61; removing a line that was never sent needs no approval. Every post-send removal records who, when, what, and reason (C5).
- OK-8 Cancelling an order is audited with who, when, previous state, reason (C5 names order cancellation). Who may cancel, and whether a reason is mandatory, is pending Q62.
- OK-9 Closed (paid/completed) and cancelled orders cannot be edited; the screen says why (legacy `backend/apps/order/tests.py:261-286`). Reopening is pending Q69.

Lifecycle
- OK-10 Every order is in exactly one lifecycle state from the set decided in Q59, and moves only along allowed transitions; an invalid transition is refused with the current state shown. Legacy set and transitions: `backend/apps/order/models.py:62-84`.
- OK-11 Each state change records who (the device for kitchen display actions, the individual for order and payment actions; C6.13), when, from, to (C5).
- OK-12 Every order has a reference staff can say aloud and search by (format pending Q64); search also matches table, customer name and item (legacy `backend/apps/order/tests.py:347-358`).

Kitchen
- OK-13 A sent order appears on every kitchen display for the restaurant within the target latency (pending Q63; suggested ≤ 3 s on normal Wi-Fi) with an audible and visual cue.
- OK-14 After a kitchen display loses and regains network, it shows every ticket sent meanwhile, with no ticket missing or duplicated (ux-principles §9).
- OK-15 Tickets show table (or takeaway name), order reference, time since sent, items with quantity, modifiers (Q45) and notes (Q65), in large text readable at arm's length.
- OK-16 Tickets are ordered oldest first (pending Q63); tickets waiting longer than a threshold are highlighted (threshold pending Q63).
- OK-17 A cook can mark ticket/line progress in one tap with ≥ 44 px targets (granularity pending Q63) and undo a mistaken "ready"/bump within a short window (pending Q63).
- OK-18 A kitchen device session can see and update kitchen tickets only; it cannot see payments, staff, or settings (C2.3, brief 01 IA-19).

Visibility and permissions
- OK-19 Order actions are gated by permissions (catalog draft `orders.*`, `kitchen.*` in `../../architecture/authorization.md`); a person lacking one sees why and who can help (ux-principles §6).
- OK-20 Orders are never visible to anyone outside the restaurant, including through a table QR link (C1.1; Q11).

## Edge and failure cases
- Waiter's phone loses network while sending → order shows "Sending…/Not sent — retry"; never shown as sent until the server confirms (Q19). On reconnect the retry cannot duplicate (OK-3).
- Waiter's shift ends with open orders → others can continue them (pending Q68); history keeps who did what.
- Waiter suspended mid-order → unsent input stays on screen but cannot be sent; open orders remain (Q40).
- Item price changes while an order is open → existing lines unchanged (OK-2, Q50).
- Menu item archived while on an open order → order and ticket still show it by name (brief 03 MN-12).
- Table moved after tickets were printed/shown → kitchen sees updated table (Q55).
- Two orders for one table / split parties → pending Q12; split bills are Phase 6 (Q14).
- Kitchen marks ready by mistake → undo (OK-17); if waiter already served, pending Q63.
- Cancelling an order whose items are already cooked → pending Q61/Q62 (waste/inventory is Phase 8, Q16).
- Business day boundary for order numbers resetting at midnight while the restaurant is open past midnight → pending Q64, Q44.
- Order open for many hours (forgotten tab) → highlighted on dashboards; no auto-close (ASSUMPTION; confirm with Q59).
- Huge order (e.g. 80 lines, banquet) → sendable; ticket scrolls; nothing truncated silently.

## Must-have vs optional
- **Must-have (v1):** OK-1–OK-20 in the forms decided by Q59–Q66; table service (Q10).
- **Optional / later:** takeaway (Q10, Q67), waiter "ready" notification (Q70), kitchen stations/courses/printing (Q13, Q22), customer QR self-ordering (Q11), discounts (`orders.discount`, Phase 6), full offline mode (Q19).
- **Out of scope here:** payment, bills, tax, refunds (Phase 6).

## Legacy behavior (unconfirmed)
- States `pending → preparing → ready → completed / cancelled`; `preparing → pending` allowed; `completed` only via payment; `ready` not editable (`backend/apps/order/models.py:62-84`, `backend/apps/order/services.py:263-266`, tests `:75-141`).
- One active order per table (`backend/apps/order/models.py:116-122`; `_ensure_no_other_active_order` `services.py:88-97`).
- Any content edit (items, notes, customer name) reset an active order to `pending` (`services.py:294-295`).
- Items already prepared / preparing could not be reduced (`services.py:150-173`).
- Tracking number `YYMMDD-<12 hex>` derived from the order id (`backend/utils/helpers.py:6-18`), because counters broke under deletes and concurrency.
- Order snapshotted restaurant tax and service-charge rates (`backend/apps/order/tests.py:442-459`).
- Customer-submitted payments waited for staff verification; staff could reject (`tests.py:288-308`, `:461-482`) — Phase 6 / Q11, Q14.
- Live updates via server-sent events (`frontend/src/hooks/useRmsEvents.js:29-31`); orders list also polled every 60 s (`frontend/src/features/orders/api.ts:50`).
- Staff (non-admin) could not settle bills or delete orders (`backend/apps/user/permissions.py:37-47`).

## Open questions
Existing, answered per change 0002: Q7 (→ C6.4, C6.17), Q19 (→ C6.7), Q33 (→ C6.13). Existing, still open: Q10 (service model), Q11 (QR self-order), Q12 (orders per table), Q13 (stations/courses/printing), Q14 (payments/splits), Q15 (tax), Q16 (inventory on cancel), Q22 (printing). From `../ux-flows.md`: UX-2 (same as Q61), UX-3 (who marks served — part of Q59), UX-6 (unsent draft survives app restart).

New (tracked in `../requirements.md`): Q59 lifecycle; Q60 additional rounds; Q61 voids after send; Q62 cancel whole order; Q63 kitchen display behaviour; Q64 order reference format; Q65 notes; Q66 sold-out at send; Q67 takeaway details; Q68 order ownership and shift handover; Q69 reopening closed orders; Q70 ready notification.
