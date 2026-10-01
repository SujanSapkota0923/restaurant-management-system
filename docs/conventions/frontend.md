# Frontend Conventions

**Status:** Proposed. The stack section reflects the scaffold built in change 0003 (ADR-0004). UX rules: `docs/product/ux-principles.md`.

## Stack-agnostic
- Mobile-first, installable web app (PWA; Q23 answered → C6.3, ADR-0004). Layout designed at 360px width first.
- Organize by feature (`features/<context>/`), with shared UI primitives in `components/ui/`.
- Server state through one data-fetching layer (query cache); no ad-hoc fetches in components.
- One API client that handles the error envelope, CSRF token, 401 → re-auth, and request IDs.
- Forms: schema validation on the client for convenience; server errors mapped to fields.
- Mutations: pending state, double-submit prevention, idempotency key for creates that support it, optimistic updates only when rollback is safe and visible.
- Permissions: the session endpoint returns effective permissions; navigation and buttons use them for display only.
- Storage: no tokens or personal data in `localStorage`/`sessionStorage`; only non-sensitive UI preferences.
- No raw HTML rendering of server/user data.
- Accessibility: semantic HTML, labelled icon buttons, focus traps in dialogs/sheets, AA contrast, 44px targets.
- i18n-ready from the start (C6.9: English only in v1): no hard-coded user-facing strings.

## Stack (ADR-0004, as built in change 0003)
- **Toolchain:** Node 24 (`frontend/.nvmrc`, `engines: >=24`), npm with a committed `package-lock.json`. Vite 8, React 19, TypeScript 6.0 (`~6.0.3`: typescript-eslint 8 supports TypeScript `<6.1`, so TypeScript 7 waits for it).
- **TypeScript:** `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noUnusedLocals/Parameters`, `verbatimModuleSyntax`. Two projects: `tsconfig.app.json` (`src/`) and `tsconfig.node.json` (`vite.config.ts`, `config/`). No `.js`/`.jsx` source files (`eslint.config.js` is the only JS file).
- **Server state:** TanStack Query 5. Defaults in `src/app/providers.tsx`: queries retry only network errors and 5xx, at most 2 retries (3 attempts); mutations are never retried automatically. A retried write needs an idempotency key.
- **Routing:** React Router 7 (`react-router` package; data router from `createBrowserRouter`). Route table in `src/app/router.tsx`. Every route tree has an `errorElement`, which never shows error details.
- **Styling:** Tailwind CSS 4 through `@tailwindcss/vite`. Design tokens are `@theme` colours in `src/styles/index.css` (placeholder palette; branding is a human decision). Body text is at least 16px. Touch targets use `min-h-11`/`min-w-11` (44px). Layouts pad for `env(safe-area-inset-*)`. Reduced motion is respected globally.
- **Strings:** every user-facing string comes from `src/i18n/messages.ts` through `t(key)`. Keys are typed, so a missing key is a type error. No i18n library until a second language is confirmed (C6.9).
- **API client** (`src/lib/api/client.ts`, the only place that calls `fetch`):
  - It accepts only relative paths that start with `/api/` and resolve, on the same origin, under `/api/`. It rejects absolute URLs, `//` URLs, backslashes, whitespace, control characters, `..` escapes and fragments by throwing `ApiPathError` before any request (change 0003 SC-40).
  - It sends `credentials: "same-origin"` and `redirect: "error"`.
  - On POST/PUT/PATCH/DELETE it sends `X-CSRFToken`, read from the CSRF cookie: `rms_csrf` in Vite dev mode, `__Host-rms_csrf` in every build. A caller-supplied CSRF header is always discarded.
  - Every failure rejects with `ApiError {status, code, message, fields, requestId}`. A body that is not exactly the `api.md` envelope becomes `unexpected_response` with a catalog message, so the UI never shows proxy or HTML error text. A network failure is `network_error` with `status: 0`. An abort is rethrown unchanged. `requestId` falls back to the `X-Request-ID` header.
  - 401 calls a handler registered with `setUnauthorizedHandler` (a no-op until 0008).
- **Env:** Vite `envDir` is `frontend/` itself, never the repository root, and `envPrefix` is `VITE_`. `VITE_*` values ship to every browser, so they never hold a secret (SC-41).
- **Dev server:** `localhost:5173` (loopback only, `strictPort`, `fs.strict`; SC-42). `/api` and `/health` are proxied to `http://127.0.0.1:8000` with the Host header preserved, so dev is same-origin like production.
- **PWA:** `vite-plugin-pwa` 1 (`generateSW`), options in `frontend/config/pwa.ts`. Manifest: `display: standalone`, 192/512 and maskable 512 icons (placeholders in `public/icons/`). The service worker precaches built static assets only. `navigateFallbackDenylist` covers `/api/` and `/health/`, and there is no runtime caching. `registerType: "prompt"`: a new version activates once all tabs are closed, never mid-task. An in-app update prompt is planned for 0008.
- **Lint and format:** ESLint 9 flat config with `typescript-eslint` `strictTypeChecked` and `eslint-plugin-react-hooks` (recommended). Restricted: the `dangerouslySetInnerHTML` JSX attribute, and `localStorage`/`sessionStorage` (global, `window.` and `globalThis.`). Prettier 3 with `printWidth: 100`.
- **Tests:** Vitest 5 with jsdom and Testing Library (`react`, `jest-dom`, `user-event`). Tests sit next to the code as `*.test.ts(x)`. Config tests live in `frontend/config/` and run in the node environment.
- **npm scripts:** `lint` (eslint + prettier check), `typecheck` (`tsc -b --noEmit`), `test` (`vitest run`), `build` (`tsc -b && vite build`), `dev`, `preview`, `format`. The build and tests also pass with `npm ci --ignore-scripts`.
- **Planned (deferred to the first change that uses them, change 0003 section 4):** react-hook-form + zod for forms (0008). Playwright for a few critical mobile-viewport journeys (0008). The in-house component set in `src/components/ui/` (sheet, button, list row, stepper, toast with undo) is built with the first screen that needs each piece.
