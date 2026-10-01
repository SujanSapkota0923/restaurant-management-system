---
name: access-control
description: Design, enforce, test and review RMS authentication and authorization — identity vs membership vs role/permission, the permission catalog, role defaults, endpoint and object-level checks, privilege escalation and staff management rules. Use whenever an action needs a permission or the permission model changes.
---

# access-control

## Purpose
Every action is allowed only for a member of the right restaurant holding the right permission — checked on the server, every time.

## When to use
- New action/endpoint/screen needing a permission; changing roles or the catalog; staff management; login/session work.

## When NOT to use
- Tenant scoping mechanics — see `tenant-isolation` (use both together).

## Inputs
- `docs/architecture/authorization.md` (model and catalog); requirements' permission criteria.

## Procedure
1. **Model.** Identity (user) ≠ membership (user in restaurant) ≠ authorization (membership → roles/permissions). Check on the membership for the current tenant, never on the user alone.
2. **Permission choice.** Reuse a catalog code if it matches the business meaning; otherwise propose a new code `<resource>.<action>` (adding a code is `APPROVAL`, since it changes the catalog).
3. **Enforce server-side** at the endpoint/command via the single authorization helper defined in `authorization.md`. Default deny: missing declaration = forbidden.
4. **Object-level checks** where rules depend on the record (e.g. a staff member may edit only their own open orders if requirements say so).
5. **Escalation guards.** A member cannot grant permissions they do not hold, cannot modify roles/memberships above their own authority, cannot remove the last owner, cannot change their own permissions.
6. **Sessions.** Permission changes and membership removal take effect on the next request (no long-lived cached grants in tokens).
7. **UI** reads the effective permission list for display only.

## Test matrix (mandatory)
For each protected action: no session → 401; member without permission → 403; member with permission → success; member of other tenant → 404; deactivated membership → denied; escalation attempts → denied.

## Safety constraints
- Never hard-code role names in checks; check permissions.
- Any change to catalog, role defaults, or the model is `APPROVAL`.

## Expected output
Permission per action in the design; enforcement + tests in implementation; findings in review.

## Verification
The test matrix exists for every protected action touched and passes.
