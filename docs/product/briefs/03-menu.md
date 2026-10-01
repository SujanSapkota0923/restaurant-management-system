# Brief 03 — Menu

**Status:** Draft (change 0002, Track A). Binding only where it cites a Confirmed rule (`../requirements.md`). "Pending Qn" = depends on an open question. Legacy notes are evidence, not requirements; legacy paths are relative to `../rms/`. Q1 (Nepal first, NPR) and Q21 (English only, i18n-ready) are answered — see C6 in `../requirements.md`.

## Goal
The restaurant keeps an accurate menu that staff can order from in seconds, and can take an item off sale the moment it runs out, without ever changing what past or in-progress orders were charged (C4 data integrity, C5 audit of price changes and deactivation).

## Actors and operating context
| Actor | Device | Frequency / pressure |
|-------|--------|----------------------|
| Owner / manager | Phone or laptop | Build menu once; price/item edits weekly; low pressure |
| Kitchen / bar | Kitchen tablet or phone | Marks items sold out mid-rush; seconds matter (who may: Q48) |
| Waiter / cashier | Phone / POS tablet | Reads the menu hundreds of times per shift; needs search, categories, availability at a glance |

## Happy paths
1. **Build menu**: Menu → add category → add item (name, price, category; optional description, image) → item appears in ordering screens immediately.
2. **Reorder**: drag or move-up/down categories and items (with a non-drag alternative, ux-principles §2) → order is saved as a whole.
3. **Change price**: open item → edit price → confirm dialog states "applies to new order lines only" (pending Q50) → saved and audited.
4. **Sold out mid-rush**: find item (search or category) → toggle "Sold out" → ordering screens show it unavailable within seconds; toggle back when restocked.
5. **Retire an item**: open item → Archive/Deactivate → it disappears from ordering; history still shows it by name (pending Q49).

## Acceptance criteria
Structure and display
- MN-1 A menu consists of categories and items; each item belongs to exactly one category (nesting pending Q46).
- MN-2 Categories and items have an explicit display order that staff ordering screens follow.
- MN-3 Reordering saves all positions together or none; an invalid reorder (e.g. same item listed twice) changes nothing. Legacy equivalent: `backend/apps/menu/tests.py:40-75`.
- MN-4 Item price is a non-negative money amount in the restaurant's currency (Q1) with the currency's decimal places; whether price 0 is allowed is pending Q51. ASSUMPTION: negative prices are never valid.
- MN-5 Staff ordering screens can find an item by name search and by category in ≤ 3 taps from the order screen (ux-principles §1).

Availability
- MN-6 An item can be marked sold out and back available in ≤ 2 taps from the menu or kitchen screen by a permitted person (permission pending Q48).
- MN-7 A sold-out item is visibly marked (colour **and** text, ux-principles §3) on all ordering screens and cannot be newly added to an order.
- MN-8 Availability changes reach other open ordering screens without manual refresh (latency target shared with Q63).
- MN-9 Scheduled availability (breakfast only, weekends) is pending Q47.

Changes, history and audit
- MN-10 Price changes, item deactivation/archiving and sold-out toggles record who, when, item, previous and new value (C5 names price change and deactivation; sold-out audit is pending Q48).
- MN-11 A price change never alters the price of order lines already on an order (pending Q50; legacy snapshot `backend/apps/order/tests.py:657-679`).
- MN-12 Renaming or archiving an item never changes how past orders display: past orders show the name and price as ordered (pending Q49/Q50).
- MN-13 An item referenced by any order (open or past) cannot be hard-deleted in a way that loses order history (C4). What the user can do instead is pending Q49.
- MN-14 A category that still contains items cannot be deleted; the message says to move or archive the items first. Legacy: `backend/apps/menu/viewsets.py:84-96`.
- MN-15 Only members with menu-management permission can create/edit/archive; price changes may require a separate permission (`menu.price_change` in permission catalog v1, approved C6.19, `../../architecture/authorization.md`; role editing pending Q42).

Modifiers and variants (pending Q45)
- MN-16 If modifiers are in v1: an item can have modifier groups (e.g. "Spice level", "Add-ons") with min/max selections and optional price deltas; required groups must be chosen before the line can be added to an order.

## Edge and failure cases
- Item marked sold out while a waiter has it in an unsent order → sending that line is refused with the item named; the rest of the order is kept on screen (whole vs partial send pending Q66). Legacy rejected the whole order: `backend/apps/order/services.py:127-137`.
- Item sold out but already on a sent order → existing lines are unaffected; quantity may stay the same but not increase (legacy `backend/apps/order/tests.py:196-226`; confirm with Q66).
- Price changed while an order is open → existing lines keep their price; newly added lines of the same item use… pending Q50 (legacy merged quantities into the existing line at the old price, `backend/apps/order/tests.py:657-679`).
- Two managers edit the same item → second save refused with "changed by <name>", no silent overwrite.
- Duplicate item names in one category → allowed or not is non-critical; ASSUMPTION: allowed with a warning.
- Very long names / descriptions → truncated in lists, full on detail; kitchen ticket shows the full name.
- Image upload fails or is slow → item saves without image; image retry offered.
- Large menus (≥ 300 items) → search stays responsive; categories collapse.
- Deactivated category with active items → items hidden from ordering too (ASSUMPTION; confirm with Q49).

## Must-have vs optional
- **Must-have (v1):** MN-1–MN-8, MN-10–MN-15.
- **Optional / later:** MN-16 modifiers (Q45 — may become must-have), scheduled availability (Q47), images, allergen/diet tags (Q51), nested categories (Q46), per-service-type pricing (Q52), stock-driven availability (Q16).
- **Out of scope:** public customer menu (Q11).

## Legacy behavior (unconfirmed)
- Categories could nest via `parent` (`backend/apps/menu/models.py:12`); items had image, `order`, `is_available`, `inventory_control_enabled` (`:21-29`).
- Items in an active order could not be deleted; the message told staff to mark them sold out instead (`backend/apps/menu/viewsets.py:111-127`).
- Soft delete on every model via base class (`backend/apps/common/models.py`) and `OrderItem.item` cascade delete (`backend/apps/order/models.py:127`) — flagged as a history-loss risk in `../../legacy/reference-assessment.md`.
- Menu readable publicly (`backend/apps/menu/viewsets.py`, `IsRestaurantAdminOrReadOnly` in `backend/apps/user/permissions.py:28-34`).
- Sold-out also derived from inventory (`menu_inventory_state`, `backend/apps/order/services.py:131`) — see Q16.

## Open questions
Existing, answered per change 0002: Q1 (NPR), Q21 (English only). Q9 answered → C6.19 (default roles, `menu.availability` code). Existing, still open: Q11 (customer QR menu), Q15 (tax-inclusive prices, rounding), Q16 (inventory-driven availability).

New (tracked in `../requirements.md`): Q45 modifiers/variants; Q46 nested categories; Q47 scheduled availability; Q48 who may mark sold out; Q49 delete vs archive; Q50 price/tax snapshot rule; Q51 item attributes (images, allergens, codes); Q52 per-service-type prices.
