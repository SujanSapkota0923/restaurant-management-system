# Documentation rules (always apply)

- Docs describe the system as built. Planned behavior is labelled `Planned` with a roadmap reference.
- A change that alters behavior, APIs, permissions, schema, config or setup updates the owning doc page (see `docs/README.md`) in the same change.
- Lasting decisions get an ADR in `docs/decisions/`. `Accepted` ADRs are never edited in substance — supersede them.
- Unconfirmed business rules go under "Open questions" in `docs/product/requirements.md`, never into the rules sections.
- Add pages only when no existing page fits; register new pages in `docs/README.md`.
- No secrets, credentials or real personal data in docs.
