# RMS developer and CI entry points (change 0003, 6.6).
# CI calls the per-side targets (*-backend, *-frontend). `make check` runs all
# checks CI runs except the DB assertions (`make db-check`); shellcheck is
# skipped if not installed.

SHELL := bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ENV_FILE := $(ROOT)/.env
BACKEND := $(ROOT)/backend
FRONTEND := $(ROOT)/frontend

# Backend commands get their environment from the env file; there is no dotenv
# dependency. --locked fails if uv.lock is out of date with pyproject.toml.
UV_RUN := cd $(BACKEND) && uv run --locked --env-file $(ENV_FILE)
MANAGE := $(UV_RUN) python manage.py

PIP_AUDIT_VERSION := 2.10.1
ZIZMOR_VERSION := 1.30.1
# ghcr.io/gitleaks/gitleaks:v8.30.1
GITLEAKS_IMAGE := ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f
# No network (security review F4); each target mounts only what it scans, read-only.
GITLEAKS_RUN := docker run --rm --network none --user "$$(id -u):$$(id -g)"
GITLEAKS := $(GITLEAKS_RUN) \
	-e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/repo \
	-v "$(ROOT):/repo:ro" $(GITLEAKS_IMAGE)

# A throwaway production environment for `check --deploy` (SC-07). The secret
# key and DB values still come from the env file; only these are overridden.
DEPLOY_ENV := DJANGO_SETTINGS_MODULE=config.settings.production DJANGO_DEBUG=false \
	DJANGO_ALLOWED_HOSTS=rms.example.test DJANGO_CSRF_TRUSTED_ORIGINS=https://rms.example.test

.PHONY: help setup init-env install install-backend install-frontend up down db-bootstrap db-check \
	migrate run run-backend run-frontend lint lint-backend lint-shell lint-frontend fmt \
	fmt-backend fmt-frontend typecheck typecheck-backend typecheck-frontend test test-backend \
	test-frontend migrations-check deploy-check audit audit-backend audit-frontend secrets \
	secrets-staged secrets-dist workflow-lint build-frontend check

help: ## List targets
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

# --- setup and services ------------------------------------------------------
setup: init-env install up migrate ## First-time setup: env file, deps, DB, migrations

init-env: ## Create the env file with random secrets if it does not exist
	$(ROOT)/scripts/dev/init-env.sh

install: install-backend install-frontend ## Install backend and frontend dependencies

install-backend:
	cd $(BACKEND) && uv sync --locked

install-frontend:
	cd $(FRONTEND) && npm ci --ignore-scripts

up: ## Start PostgreSQL and wait until it is healthy
	cd $(ROOT) && docker compose up -d --wait db

down: ## Stop services (keeps the DB volume)
	cd $(ROOT) && docker compose down

db-bootstrap: ## Re-run the role/DB bootstrap in the running container (idempotent)
	cd $(ROOT) && docker compose exec -T db /docker-entrypoint-initdb.d/10-bootstrap.sh

db-check: ## Assert loopback port, password auth and bootstrap idempotency
	$(ROOT)/scripts/ci/db-check.sh

migrate: ## Apply migrations as the migrator role
	$(MANAGE) migrate --database migrator

run: ## Run backend and frontend dev servers
	$(MAKE) -j2 run-backend run-frontend

run-backend:
	$(MANAGE) runserver 127.0.0.1:8000

run-frontend:
	cd $(FRONTEND) && npm run dev

# --- checks -------------------------------------------------------------------
lint: lint-backend lint-shell lint-frontend ## Lint and format-check everything

lint-backend:
	cd $(BACKEND) && uv run --locked ruff check .
	cd $(BACKEND) && uv run --locked ruff format --check .

# shellcheck is preinstalled on GitHub's Ubuntu runners. Locally it is skipped
# with a notice when missing; CI sets REQUIRE_SHELLCHECK=1 so it cannot skip.
lint-shell:
	@if command -v shellcheck >/dev/null; then \
		shellcheck $(ROOT)/scripts/*/*.sh; \
	elif [[ "$${REQUIRE_SHELLCHECK:-0}" == "1" ]]; then \
		echo "shellcheck is required but not installed" >&2; exit 1; \
	else \
		echo "lint-shell: shellcheck not installed; skipped (CI runs it)"; \
	fi

lint-frontend:
	cd $(FRONTEND) && npm run lint

fmt: fmt-backend fmt-frontend ## Apply formatters and autofixes

fmt-backend:
	cd $(BACKEND) && uv run --locked ruff format .
	cd $(BACKEND) && uv run --locked ruff check --fix .

fmt-frontend:
	cd $(FRONTEND) && npm run format

typecheck: typecheck-backend typecheck-frontend ## Type-check everything

typecheck-backend:
	$(UV_RUN) mypy .

typecheck-frontend:
	cd $(FRONTEND) && npm run typecheck

test: test-backend test-frontend ## Run all tests

test-backend: ## Backend tests (extra args: PYTEST_ARGS=...)
	$(UV_RUN) pytest $(PYTEST_ARGS)

test-frontend:
	cd $(FRONTEND) && npm run test

migrations-check: ## Fail if models and migrations are out of sync
	$(MANAGE) makemigrations --check --dry-run

deploy-check: ## check --deploy on production settings; must also fail with debug on
	cd $(BACKEND) && $(DEPLOY_ENV) uv run --locked --env-file $(ENV_FILE) \
		python manage.py check --deploy --fail-level WARNING
	@err="$$(mktemp)"; trap 'rm -f "$$err"' EXIT; \
	if (cd $(BACKEND) && $(DEPLOY_ENV) DJANGO_DEBUG=true uv run --locked --env-file $(ENV_FILE) \
		python manage.py check --deploy --fail-level WARNING) >/dev/null 2>"$$err"; then \
		echo "deploy-check: production settings started with DJANGO_DEBUG=true" >&2; exit 1; \
	elif ! grep -qF 'DJANGO_DEBUG must be false' "$$err"; then \
		echo "deploy-check: the DJANGO_DEBUG=true run failed, but not with the debug refusal;" \
			"re-run it by hand to see why" >&2; exit 1; \
	else echo "deploy-check: production settings refuse DJANGO_DEBUG=true"; fi

audit: audit-backend audit-frontend ## Dependency vulnerability audit (installs nothing)

audit-backend:
	@req="$$(mktemp)"; trap 'rm -f "$$req"' EXIT; \
	cd $(BACKEND) && uv export --locked --all-groups --format requirements-txt \
		--no-emit-project --quiet --output-file "$$req" && \
	uvx pip-audit==$(PIP_AUDIT_VERSION) --strict --require-hashes --disable-pip -r "$$req"

audit-frontend:
	cd $(FRONTEND) && npm audit --omit=dev --audit-level=low
	cd $(FRONTEND) && npm audit --audit-level=high

secrets: ## gitleaks over the full git history (redacted)
	$(GITLEAKS) git --redact --verbose --no-banner /repo

secrets-staged: ## gitleaks over staged changes (run before committing)
	$(GITLEAKS) git --pre-commit --staged --redact --verbose --no-banner /repo

# Mounts only frontend/dist. The existence check stops docker from creating a
# missing bind-mount source as an empty directory.
secrets-dist: ## gitleaks over the built frontend bundle (SC-41; run build-frontend first)
	@test -d $(FRONTEND)/dist || { echo "secrets-dist: frontend/dist missing; run make build-frontend" >&2; exit 1; }
	$(GITLEAKS_RUN) -v "$(FRONTEND)/dist:/dist:ro" $(GITLEAKS_IMAGE) \
		dir --redact --verbose --no-banner /dist

# The policy script must pass the real workflows and reject every bad fixture
# in scripts/ci/testdata/ (security review F2).
workflow-lint: ## zizmor + workflow policy check (SC-30..33) + its self-test
	cd $(ROOT) && uvx zizmor==$(ZIZMOR_VERSION) --offline .github/workflows
	$(ROOT)/scripts/ci/check-workflows.sh $(ROOT)/.github/workflows/*.yml
	$(ROOT)/scripts/ci/test-check-workflows.sh

build-frontend:
	cd $(FRONTEND) && npm run build

# Serial order matters: secrets-dist scans the output of build-frontend.
# db-check is left out: it needs the DB container and re-runs the bootstrap.
CHECK_TARGETS := lint typecheck migrations-check test deploy-check audit secrets build-frontend \
	secrets-dist workflow-lint
check: $(CHECK_TARGETS) ## All checks CI runs except the DB assertions (make db-check); shellcheck is skipped if not installed
