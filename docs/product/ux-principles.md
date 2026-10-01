# UX Principles

These principles bind every workflow. The `ux-designer` agent applies them; the `mobile-first-ux` skill holds the procedure.

## 1. Shortest safe path
For each workflow answer: what is the user's goal, what do they need to see, what is the shortest safe path, which steps merge, which defaults can be smart, which actions can be inline, what must stay visible. Frequent operations (add item, send to kitchen, mark ready, take payment) aim for ≤ 3 taps from their home screen where safe.

## 2. Mobile first, touch first
Design at 360×640 first and scale up — never shrink a desktop layout. Primary actions within thumb reach. Touch targets ≥ 44×44 px. No hover-only or gesture-only actions. Bottom sheets for quick edits; context (e.g. the current order) stays visible.

## 3. Built for the rush
Users are busy, distracted, standing, sometimes with wet or gloved hands. Large text, high contrast, glanceable status using colour **and** text/icon, minimal typing (steppers, chips, recent items, search).

## 4. Predictable
Every tap gets immediate feedback. Users always know: what happened, what happens next, whether it succeeded or failed, whether it can be undone. No silent failure, no silent data loss.

## 5. Confirmation by consequence
- Reversible → act immediately + undo.
- Irreversible, money-affecting or bulk → confirm dialog that states the consequence in plain words.
- Routine actions → no confirmation.

## 6. Every state designed
Loading (skeletons), empty (next step), error (what failed, what to do, input kept), slow/offline (pending indicator, retry), success (brief, non-blocking), permission-denied (why, who can help).

## 7. Safety is not negotiable
Never remove an authorization check, money confirmation or audit step to save a tap. Find a faster safe design instead.

## 8. Accessible
WCAG 2.2 AA contrast, labelled controls, screen-reader order, focus management in sheets/dialogs, respects reduced motion and text scaling.

## 9. Kitchen and fixed displays
Readable at arm's length, very large targets, no small menus, status visible at a glance, new tickets impossible to miss, tolerant of flaky Wi-Fi without missing or duplicating tickets.
