# Legacy Reference Assessment (`../rms`)

Assessed 2026-09-30 from the working tree of `../rms` (55 commits, last: "push garna ta maan xaina yo inventory"). This is a reading of the code, not of a running system. Nothing was executed.

`../rms` is a **reference only**. The new RMS is a rebuild (ADR-0002). Nothing is copied without a change record justifying it.

## What exists

| Area | Stack / shape | Evidence |
|------|---------------|----------|
| Backend | Django 5.2, DRF 3.16, django-tenants 3.9 (schema-per-tenant on PostgreSQL 16), SimpleJWT, Celery + Redis, uvicorn ASGI | `backend/requirements.txt`, `backend/core/settings.py` |
| Frontend | React 18 + Vite 5, Tailwind 3, React Router 7, TanStack Query 5, react-hook-form, zod; mostly JSX, some TS | `frontend/package.json` |
| Apps | `restaurant` (tenant + settings), `user`, `menu`, `order` (tables, reservations, orders, payments, idempotency), `inventory` (items, lots, recipes, movements, allocations), `schedule` (staff shifts), `audit` (audit log + outbox events + SSE streaming), `common` (base model with soft delete) | `backend/apps/*` |
| Screens | Dashboard, Orders, POS, Menu, Tables, Staff, Billing, Schedule, Reports, Settings, History, Inventory, customer QR menu / confirmation / payment | `frontend/src/App.jsx` |
| Infra | docker-compose (postgres, redis, backend, worker, frontend), Makefile | `docker-compose.yml`, `Makefile` |
| Tests | Django tests per app (order tests largest), a few Vitest tests | `backend/apps/*/tests.py`, `frontend/src/**/*.test.*` |

## Worth preserving (as ideas, re-implemented under the new rules)

- **Server-side tenant separation** as a first-class concern (it chose schema-per-tenant; the new strategy is decided in ADR-0003).
- **HttpOnly cookie auth + CSRF check for cookie-authenticated unsafe methods** (`apps/audit/authentication.py`, `apps/user/auth.py`).
- **Transactional service layer** for orders with **idempotency records**, **advisory locks** and an **optimistic `version`** field (`apps/order/services.py`, `apps/order/models.py`).
- **Partial unique constraint**: one active order per table (`apps/order/models.py`) — the rule itself needs product confirmation.
- **Transactional outbox** (`DomainEvent`) feeding live updates and audit (`apps/audit/models.py`, `apps/audit/services.py`).
- **Price/tax snapshot on order items and orders** (`OrderItem.price`, `Order.tax_rate`).
- **Append-only stock movements with lots** and per-order inventory allocation (`apps/inventory/models.py`).
- **Revocable signed table QR tokens** with a version counter (`apps/order/viewsets.py` `table_from_token`).
- **Request ID middleware** and a standard error envelope (`core/middleware.py`, `core/exceptions.py`, `frontend/src/api/client.ts`).
- Product surface: the screen list above is a useful checklist for requirements discovery.

## Discard / do not repeat

| Problem | Evidence | Why it matters |
|---------|----------|----------------|
| Identity fused with tenancy: `User.restaurant` FK and a `role` field of `admin`/`staff` | `apps/user/models.py` | One user = one restaurant; roles hard-coded; violates identity/membership/authorization separation |
| Ad-hoc permissions: `inventory_permissions` JSON list on user; everything else by `role == "admin"` | `apps/user/models.py`, `apps/user/permissions.py` | Not granular, not extensible, role-name checks |
| `apps.user` listed in both `SHARED_APPS` and `TENANT_APPS` | `core/settings.py` | User tables exist in public and every tenant schema — ambiguous source of truth |
| Secret key and DB password committed in `docker-compose.yml`, `DEBUG=True` there | `docker-compose.yml` | Secrets in Git; unsafe defaults |
| CORS allow-all when `DEBUG` | `core/settings.py` (`CORS_ORIGIN_ALLOW_ALL` default = DEBUG) | Combined with credentials, easy to ship misconfigured |
| Public (`AllowAny`/read-only-for-anyone) endpoints for menu and settings without documented threat model | `apps/menu/viewsets.py`, `apps/restaurant/viewsets.py` | Unreviewed public surface |
| No rate limiting, no email verification, no password reset flow | grep over backend | Security baseline gaps |
| Staff cannot change own password (endpoint restricted to admin) | `apps/user/viewsets.py` `change_own_password` | Product/security gap |
| User profile cached in `localStorage` | `frontend/src/auth.js` | Tokens were moved to cookies (good) but the pattern invites regressions; keep only non-sensitive UI state client-side |
| Generic soft delete on every model via base class, default manager hides inactive rows | `apps/common/models.py`, `managers.py` | Soft delete everywhere hides data unpredictably; FK cascades still hard-delete |
| `Table` → `Order` `on_delete=CASCADE`, `OrderItem.item` `CASCADE` | `apps/order/models.py` | Deleting a table/menu item could delete order history |
| Audit via generic model signals capturing all field changes | `apps/audit/signals.py` | Noisy, not business-meaningful, may capture sensitive fields |
| Business rules embedded in model methods (shift enforcement on `User`) | `apps/user/models.py` | Mixed responsibilities |
| Commit history suggests unverified large AI-generated changes ("very risky point… khasai check garya xaina") | `git log` | Treat inventory and recent code as unverified |

## Rebuild

Everything, under the new engineering system: requirements → domain → tenancy/authz foundations → features by roadmap phase. Legacy tests may be read to discover edge cases the old team met.

## Open questions surfaced by the legacy system

These are features the legacy system has but the new brief does not list. Each needs a product decision (tracked in `docs/product/requirements.md`):

- Customer self-ordering via table QR codes, and customer-side payment submission.
- Staff scheduling/shifts and automatic off-duty enforcement.
- Payment verification workflow (QR payment submitted → staff verifies/rejects).
- Recipe-based inventory consumption with FIFO lots and costing.
- Nepal defaults (currency `Rs`, timezone `Asia/Kathmandu`, 10% tax default) — target market and tax/billing compliance.
