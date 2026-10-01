---
paths:
  - "frontend/**"
---

# Frontend rules

Conventions: `docs/conventions/frontend.md`. UX: `docs/product/ux-principles.md`, `mobile-first-ux` skill.

- Build for a 360px-wide touch screen first. No hover-only interactions. Touch targets ≥ 44×44 px.
- Every data view handles loading, empty, error, offline/slow and permission-denied states.
- Mutations: disable double submit, show pending state, surface server errors per field, never silently drop user input.
- Reversible actions use undo; irreversible or money-affecting actions use a confirm that states the consequence.
- Permission checks in UI are display-only; the server is the authority.
- Never store tokens or secrets in `localStorage`/`sessionStorage`. Cache only non-sensitive UI state there.
- Never render untrusted HTML. No `dangerouslySetInnerHTML` without an approved sanitizer.
- Reuse existing components before creating new ones. No new UI library without `REVIEW`.
- Accessible by default: semantic elements, labels on icon buttons, focus management in sheets/dialogs, AA contrast.
