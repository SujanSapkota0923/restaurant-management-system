---
name: mobile-first-ux
description: Design and review RMS workflows and screens for mobile-first, touch-first, low-attention restaurant use — minimal interactions, intelligent defaults, inline actions, clear state feedback, confirmation by reversibility, accessibility and flaky-network behavior. Use for any new or changed user-facing workflow or component.
---

# mobile-first-ux

## Purpose
Common restaurant operations take the fewest safe taps, on a phone, under pressure.

## When to use
- Designing a workflow/screen; implementing UI; reviewing UI.

## When NOT to use
- Backend-only changes; visual branding decisions (human).

## Inputs
- Requirements; `docs/product/ux-principles.md`; `docs/conventions/frontend.md`; existing components.

## Procedure
1. **Frame.** User goal, role, device, how often per shift, time pressure, one- or two-handed.
2. **Minimum information.** List what the user must see to decide; everything else is secondary or hidden.
3. **Shortest safe path.** Write the flow with tap counts. For each step ask: can it merge, default, or happen inline? Target: frequent operations (add item, send to kitchen, mark ready, take payment) in ≤ 3 taps from their home screen where safe.
4. **Layout.** Design at 360×640 first. Primary actions in thumb reach (bottom). Bottom sheets over full-page navigation for quick edits. Keep context visible (the order stays on screen while adding items).
5. **States.** Specify loading (skeletons, not spinners over whole screen), empty (what to do next), error (what failed, what to do, data kept), offline/slow (queued/pending indicator; never silent loss), success (brief, non-blocking), permission-denied (why, who can help).
6. **Confirmation by reversibility.** Reversible → do it + undo toast. Irreversible, money or bulk → confirm dialog stating the consequence in plain words. Never confirm routine actions.
7. **Feedback & predictability.** Every tap gets immediate visual response; pending mutations show state; results show what changed.
8. **Accessibility.** Touch targets ≥ 44×44 px with spacing; contrast WCAG AA; text ≥ 16px for body; labels for icons; focus handling in sheets/dialogs; no hover-only or gesture-only actions; respects reduced motion.
9. **Kitchen / fixed displays.** Large type, glanceable status by color **and** text/icon, big tap targets, no small menus, readable at arm's length.

## Safety constraints
- Never remove an authorization, confirmation-for-money, or audit step to save taps.
- Do not add product scope; suggest it in the change record.

## Expected output
Flow (numbered steps + tap counts + states) in the Design section; in reviews, deviations by screen/step.

## Verification
Walk the flow on a 360px viewport: every state reachable, every action ≤ documented taps, keyboard/screen-reader operable.
