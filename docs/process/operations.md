# Operations: CI/CD, Deployment, Observability

**Status:** Local development and CI are built (change 0003). Staging, production, deployment and observability tooling are **Planned** (Phase 10). Every production infrastructure change is `APPROVAL`.

## Environments
local (Docker) → CI (ephemeral) → staging (production-like, fake data) → production. No production data outside production.

## Local development (as built in change 0003)
**Prerequisites:** Docker with Compose v2, uv, Node 24 or newer (`frontend/.nvmrc`), openssl, GNU make, bash.

| Command | What it does |
|---------|--------------|
| `make setup` | `init-env`, install backend (`uv sync --locked`) and frontend (`npm ci --ignore-scripts`) dependencies, `up`, `migrate` |
| `make init-env` | Creates the root env file from `.env.example` and replaces every placeholder secret with a random value (`scripts/dev/init-env.sh`). File mode 0600. It never prints a value and never overwrites an existing file |
| `make up` / `make down` | Start PostgreSQL and wait until it is healthy / stop it. `down` keeps the data volume |
| `make migrate` | `manage.py migrate --database migrator` (the migrator role owns schema objects) |
| `make run` | Backend on `127.0.0.1:8000` and the Vite dev server (proxies `/api` and `/health` to the backend with the Host header preserved) |
| `make lint` / `make fmt` | ruff + shellcheck + ESLint/Prettier checks / autofix |
| `make typecheck` | mypy (strict) and `tsc -b --noEmit` |
| `make test` | pytest (as the app role) and Vitest |
| `make migrations-check` | `makemigrations --check --dry-run`, with the local and with the test settings (the test settings add the test-only probe app) |
| `make migrations-roundtrip` | On a throwaway DB `rms_roundtrip` (created by the migrator from `rms_template`, ACL locked down, dropped at the end): migrate up, reverse every app to zero, check nothing is left, migrate up again, run the catalog check. Refuses any other DB name and never connects to the dev DB (change 0004) |
| `make catalog-check` | The tenant-isolation catalog check on the dev DB, read-only, as the app role. Needs `make migrate` first; zero tenant tables is allowed there (change 0004) |
| `make deploy-check` | `check --deploy --fail-level WARNING` on the production settings with throwaway values; it must also refuse `DJANGO_DEBUG=true` |
| `make audit` | pip-audit and npm audit (reads lockfiles only) |
| `make secrets` / `make secrets-staged` / `make secrets-dist` | gitleaks over the git history / over staged changes (run before every commit) / over the built `frontend/dist` (run `make build-frontend` first) |
| `make workflow-lint` | zizmor, the workflow policy script on the real workflows, and the script's self-test (`scripts/ci/test-check-workflows.sh`: every fixture in `scripts/ci/testdata/` must be rejected) |
| `make db-check` / `make db-bootstrap` | DB assertions (below) / re-run the role bootstrap (idempotent) |
| `make check` | All checks CI runs except the DB assertions (`make db-check`) and `make catalog-check` (it needs a migrated dev DB; the same check runs in the tests and the round trip); shellcheck is skipped if not installed (CI requires it) |

**Env file.** Backend commands load it with `uv run --env-file`; there is no dotenv dependency. Values in the shell environment take precedence over the file. Never commit it (`.gitignore`), never print it. Never run `docker compose config`, because it prints interpolated secrets. To rotate local secrets, stop the stack, delete the env file and the DB volume (`docker compose down -v`, which deletes local data), then run `make setup` again.

**Database** (`compose.yaml`, service `db`):
- `postgres:16`, pinned by digest. The port is published on `127.0.0.1:5432` only. Password auth is `scram-sha-256` for TCP. The container receives only `POSTGRES_PASSWORD`, `DB_NAME`, `DB_APP_*` and `DB_MIGRATOR_*`, never the whole env file.
- On first start, `scripts/db/bootstrap.sh` creates:
  - `rms_migrator`: LOGIN, CREATEDB (local/CI only, for the test DB), no superuser/createrole/bypassrls;
  - `rms_app`: LOGIN, NOINHERIT, member of nothing, no createdb/createrole/bypassrls, `statement_timeout=15s`, `idle_in_transaction_session_timeout=30s`;
  - `rms_template`, owned by the migrator: `public` is owned by the migrator, PUBLIC has no access, the app role has USAGE, and default privileges give the app role DML on the migrator's tables and sequences;
  - the dev DB `rms`, created from the template, with CONNECT for the two roles only;
  - the maintenance DBs locked down (change 0004): PUBLIC has no privilege on `postgres` or `template1`, the migrator keeps CONNECT on `postgres` (Django connects there to create and drop the test and round-trip DBs), and the app role can connect to neither.
- A bootstrap change reaches an existing container only after `make down` and `make up` (the script is a single-file bind mount, which keeps pointing at the old file after an editor replaces it; the data volume is kept), followed by `make db-bootstrap`.
- Passwords reach psql only through `\getenv` (never argv). Statement logging is off for the bootstrap session, and errors are printed tersely, so a failing statement is not echoed.
- Tests create `test_rms` from the template as the migrator, then connect as the app role (`docs/conventions/backend.md` "Tests").

## CI (as built in changes 0003 and 0004)
- `.github/workflows/ci.yml`, four jobs: `backend`, `frontend`, `audit`, `secrets` (contents in `docs/process/testing-strategy.md`). Triggers are `push` and `pull_request` only. `permissions: contents: read`, no job raises it, no `secrets.*`. Every checkout uses `persist-credentials: false`. Superseded runs are cancelled. Each job has a timeout.
- CI runs PostgreSQL through the same `compose.yaml` as local development, with an env file generated per run. The generated secrets are registered with `::add-mask::`. Nothing else prints them. On failure, only `docker compose logs db` is printed.
- DB assertions (`scripts/ci/db-check.sh`): the port is bound to `127.0.0.1` only; a TCP login as the app role with a wrong password is rejected; re-running the bootstrap leaves roles, memberships, database/schema ACLs and default privileges unchanged; `postgres` and `template1` grant nothing to PUBLIC and the app role cannot connect to them.
- Migrations and isolation (change 0004): `make migrations-check` (local and test settings), then `make migrate` on the per-run dev DB, `make catalog-check` on it, and `make migrations-roundtrip`, before the tests.
- After the tests, the working tree must be clean (`git status --porcelain`).
- **Pins** (SC-32). Every action is pinned to a commit SHA with a version comment. Resolve a new SHA with `git ls-remote https://github.com/<owner>/<repo> refs/tags/<tag>`; never type one by hand. Images are pinned by digest: postgres in `compose.yaml`, gitleaks in the `Makefile`. Read a digest with `docker pull <image>:<tag>` then `docker inspect --format '{{json .RepoDigests}}' <image>:<tag>`. The uv, pip-audit and zizmor versions are exact (`ci.yml` `UV_VERSION`, `Makefile`).
- **Workflow lint** (SC-30..33). zizmor runs with `.github/zizmor.yml` (hash-pin for every action), plus `scripts/ci/check-workflows.sh` (forbidden triggers in block or inline `on:` form, permissions, secrets, persisted credentials, pins, `${{ }}` in `run:`, artifact upload, env dumps such as `env`, `printenv`, bare `set`/`export`/`declare`, `export -p`, `declare -p`, `compgen -v`, and printing an env file with `cat`/`head`/`tail` and similar). The script is line-based; its self-test runs one bad-workflow fixture per rule from `scripts/ci/testdata/` (never under `.github/workflows/`, where GitHub would run them), and each must fail with its expected message. A rule change comes with a fixture. Relaxing either is a security-engineer `REVIEW`.
- **Impostor-commit check for action SHAs** (security review F6). zizmor runs `--offline` in CI, because an online run needs a token and CI holds none (SC-31). So every change to a `uses:` SHA, Dependabot PRs included, needs an impostor-commit check before merge: either a local online `zizmor` run (with a read-only token) or `git ls-remote https://github.com/<owner>/<repo> refs/tags/<tag>` returning the pinned SHA. The reviewer records which check was done, and its result, in the PR.
- **Audit thresholds** (SC-35). `pip-audit --strict` fails on any finding. `npm audit --omit=dev --audit-level=low` and a full-tree `npm audit --audit-level=high` both block. There is no allow-list. Any ignore entry needs a `docs/risks.md` acceptance by the human, with an expiry date.
- **gitleaks** (SC-36) always runs with `--redact` and `--network none`, over the full history (`fetch-depth: 0`), with the repository mounted read-only. `secrets-dist` mounts only `frontend/dist`, read-only. Any `.gitleaks.toml` allow-list entry is path-scoped and a security-engineer `REVIEW`.
- **Dependabot** (`.github/dependabot.yml`): weekly updates for `uv` (`/backend`), `npm` (`/frontend`), `github-actions` and `docker-compose` (the postgres digest in `compose.yaml`). Version updates have a 7-day cooldown; security updates are not delayed. There is no auto-merge: each update PR is reviewed and must pass CI.

### Required GitHub repository settings (SC-38, human)
Code cannot enforce these. Until they are applied, CI is advisory:
1. A branch ruleset on `main` that requires the checks `backend`, `frontend`, `audit` and `secrets` to pass, plus a review.
2. Actions → "Fork pull request workflows": require approval for all outside collaborators.
3. Actions → "Workflow permissions": default `GITHUB_TOKEN` permission "Read repository contents".

As of 2026-10-01 no GitHub repository exists, so these settings are not applied (change 0003, human approval note).

## CI/CD principles
- Every PR: lint, type-check, tests, migration check, dependency audit, secret scan.
- Build once, promote the same artifact through staging to production.
- Migrations run as a separate, explicit deploy step with the migration (owner) DB role; destructive migrations need recorded approval.
- Production deploys require human approval.

## Configuration and secrets
- Environment variables come from a secret manager. `.env.example` documents names only, with placeholder values.
- The production settings refuse to start with debug on, a missing or weak secret key, an empty or wildcard `ALLOWED_HOSTS`, insecure cookies, or the other rules in `backend/config/validation.py` (built in 0003).
- `DJANGO_SECURE_PROXY_SSL_HEADER` (format `HTTP_<NAME>=https`) may be set **only behind a reverse proxy that always overwrites that header**. Otherwise a client can claim HTTPS. Verifying this is a Phase 10 deploy check (SC-06).
- **Planned** (Phase 10): the `/health/*` endpoints are unauthenticated and not rate-limited (R25, accepted until Phase 10). Before deployment, either only the platform's health checker can reach readiness, or the edge rate-limits `/health/*` per IP.

## Observability
- Structured JSON logs with `request_id`, `tenant_id`, `membership_id`; redaction of secrets and personal data. Built in 0003 for secrets; `tenant_id`/`membership_id` are filled from 0004/0005; personal-data redaction is **Planned** (0005).
- Error tracking with PII scrubbing. **Planned.**
- Metrics: request latency/error rate per endpoint, job queue depth/latency, DB pool saturation, kitchen event delivery latency. **Planned.**
- Health: `GET /health/live` (process up, no DB) and `GET /health/ready` (`SELECT 1` on the app connection, 5 s connect timeout; 503 `not_ready` on failure). Both return `{"status":"ok"}` with no version or host data. Built in 0003.
- Alerts on error-rate spikes, queue backlog, failed backups. **Planned.**

## Data protection
Encrypted automated backups; point-in-time recovery; restore drill before launch and periodically; targets in `docs/architecture/overview.md`.

## Open decisions (Phase 2/10)
Hosting provider, container orchestration, managed PostgreSQL, job-queue backend, error-tracking and metrics tools, CDN for static assets and uploads.
