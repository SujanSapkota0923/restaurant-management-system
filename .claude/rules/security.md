# Security rules (always apply)

- Treat every request as hostile. Validate all input server-side with allow-listed fields; never trust client-supplied prices, totals, permissions or tenant IDs.
- Every endpoint declares an explicit permission. No default-open endpoints. Unauthenticated endpoints need a threat-model entry in the change record.
- Auth tokens/session IDs live only in `HttpOnly` + `Secure` + `SameSite` cookies. Never in `localStorage`, `sessionStorage`, URLs or JS-readable cookies.
- Cookie-authenticated unsafe requests are CSRF-protected. Do not add CSRF exemptions.
- ORM or parameterized SQL only. No string-built queries, no `eval`, no unsafe deserialization (pickle, full YAML loader).
- Never render untrusted HTML. No `dangerouslySetInnerHTML` / `mark_safe` / `|safe` on user data.
- Error responses never include stack traces, SQL, file paths, secrets, or hints about other tenants' data.
- Production config: debug off, strict allowed hosts, CORS allow-list (never `*` with credentials), secure cookies, HSTS.
- Uploads: size + content-type allow-list verified by content, re-encoded, random names, never executable, tenant-scoped storage path.
- Webhooks: signature verified (constant-time), timestamp window, replay protection by event ID, idempotent handling.
- Rate-limit login, signup, password reset, verification and public endpoints. Uniform responses to prevent account enumeration.
- Never disable, bypass, mock out or comment out a security control to make something work. Report `BLOCKED` instead.
