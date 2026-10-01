---
name: secure-coding
description: Secure implementation checklist for RMS backend and frontend code — input validation, output encoding, query safety, secrets, cookies/CSRF/CORS, uploads, webhooks, rate limits, error handling and logging hygiene. Use while writing any code that handles input, output, auth, files, external calls or configuration.
---

# secure-coding

## Purpose
Avoid introducing the common vulnerability classes in the first place.

## When to use
- Implementing any L1+ code. Reviewers use it as a reference checklist.

## When NOT to use
- Threat modeling a design — see `threat-modeling`.

## Checklist
**Input**
- Validate every request on the server: types, ranges, lengths, enums, allow-listed fields. Reject unknown fields for write endpoints.
- Never trust client-computed totals, prices, tax or permissions; recompute on the server.

**Data access**
- ORM or parameterized queries only. No string-built SQL, no dynamic column names from input.
- Tenant-scoped access path only (`tenant-isolation`).

**Output**
- Rely on framework auto-escaping; never render untrusted HTML. Set content types explicitly.
- Error responses use the standard envelope; no stack traces, SQL or internal IDs of other tenants.

**Auth and sessions**
- Tokens/session IDs only in `HttpOnly`, `Secure`, `SameSite` cookies. Never `localStorage`.
- Cookie-authenticated unsafe methods require CSRF protection.
- Rotate the session on login and privilege change; invalidate on logout and password change.
- Password hashing with the framework's strong default (Argon2id or PBKDF2 with current iterations).
- Uniform responses for login, signup and password reset to prevent account enumeration; rate-limit them.

**Config and secrets**
- Secrets from environment/secret manager only. Never in code, fixtures, tests, logs, docs or error messages.
- Production: debug off, strict allowed hosts, CORS allow-list (no wildcard with credentials), HSTS, secure cookies.

**Files**
- Uploads: size limit, allow-listed types verified by content (not just extension), re-encode images, random server-side names, stored outside the web root or in object storage with tenant-scoped paths, never executed.

**External calls**
- Webhooks: verify signature with constant-time compare, check timestamp window, store event IDs to reject replays, process idempotently.
- Outbound requests from user-supplied URLs: allow-list hosts (SSRF).
- Never deserialize untrusted data with unsafe formats (pickle, YAML full loader).

**Abuse**
- Rate-limit authentication, public endpoints, and expensive operations.
- Bound list sizes and report ranges.

**Logging**
- Log security events (login, failure, permission denied, role change) with request ID and tenant ID.
- Never log passwords, tokens, cookies, full card/payment data, or full request bodies of auth endpoints.

## Safety constraints
- If a checklist item conflicts with the design, stop and report — do not skip it silently.

## Verification
Relevant checklist items are covered by tests (validation, permission, CSRF, enumeration responses, upload rejection, webhook replay).
