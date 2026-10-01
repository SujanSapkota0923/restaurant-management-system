# Authorization rules (always apply)

Model and permission catalog: `docs/architecture/authorization.md`.

- Keep identity (user), membership (user ↔ restaurant) and authorization (membership → roles/permissions) separate. Check permissions on the membership (or device session) the request acts through — the one for the restaurant in the URL path — not on the user.
- Check permission codes (`orders.cancel`), never role names (`if role == "admin"`).
- Enforce on the server through the single authorization helper. Frontend checks are display-only.
- Default deny: an action without a declared permission is forbidden.
- Guard escalation: no granting permissions you lack, no editing your own grants, no removing the last owner, no acting on memberships above your authority.
- Permission and membership changes take effect on the next request; do not embed grants in long-lived tokens.
- Adding, removing or renaming a permission code, or changing role defaults, is `APPROVAL`.
- Every protected action has tests: 401, 403, cross-tenant 404, deactivated membership, success.
