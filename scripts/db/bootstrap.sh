#!/usr/bin/env bash
# Create the RMS database roles, the template DB and the dev DB (change 0003, 6.5).
#
# Runs inside the postgres container as the container superuser:
#   - automatically, as /docker-entrypoint-initdb.d/10-bootstrap.sh on first start;
#   - again on demand (`make db-bootstrap`); it is idempotent.
#
# Security (SC-22):
#   - never `set -x`; passwords are read inside psql with \getenv from the
#     container environment, so they are never on argv and never echoed;
#   - statement logging is switched off for this session before any statement
#     that carries a password, and psql's error verbosity is terse so a failing
#     statement is not echoed back;
#   - names are validated here, then passed with -v and quoted by psql as :"name"
#     / :'name'; conditional DDL uses format(%I) + \gexec. No SQL is built by the
#     shell and there are no DO blocks.
set -euo pipefail

: "${DB_NAME:?DB_NAME is required}"
: "${DB_APP_USER:?DB_APP_USER is required}"
: "${DB_MIGRATOR_USER:?DB_MIGRATOR_USER is required}"
[[ -n "${DB_APP_PASSWORD:-}" ]] || { echo "bootstrap: DB_APP_PASSWORD is required" >&2; exit 1; }
[[ -n "${DB_MIGRATOR_PASSWORD:-}" ]] || { echo "bootstrap: DB_MIGRATOR_PASSWORD is required" >&2; exit 1; }

template_db="rms_template"
superuser="${POSTGRES_USER:-postgres}"
name_re='^[a-z_][a-z0-9_]{0,62}$'
for name in "$DB_NAME" "$DB_APP_USER" "$DB_MIGRATOR_USER" "$template_db" "$superuser"; do
  if [[ ! "$name" =~ $name_re ]]; then
    echo "bootstrap: a role or database name does not match $name_re" >&2
    exit 1
  fi
done

psql --no-psqlrc --set ON_ERROR_STOP=1 --quiet \
  --username "$superuser" --dbname postgres \
  --set app_role="$DB_APP_USER" \
  --set mig_role="$DB_MIGRATOR_USER" \
  --set dev_db="$DB_NAME" \
  --set tpl_db="$template_db" <<'SQL'
\set VERBOSITY terse
\set SHOW_CONTEXT never
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
SET password_encryption = 'scram-sha-256';
\getenv app_pw DB_APP_PASSWORD
\getenv mig_pw DB_MIGRATOR_PASSWORD

-- 1. Migrator: owns schema objects; CREATEDB only because local/CI create the test DB.
SELECT format('CREATE ROLE %I', :'mig_role')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'mig_role') \gexec
ALTER ROLE :"mig_role" WITH LOGIN NOSUPERUSER NOCREATEROLE NOBYPASSRLS NOREPLICATION CREATEDB;
ALTER ROLE :"mig_role" WITH PASSWORD :'mig_pw';

-- 2. App role: DML only, member of nothing, bounded statements (dev values, C3-10).
SELECT format('CREATE ROLE %I', :'app_role')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_role') \gexec
ALTER ROLE :"app_role" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION NOINHERIT;
ALTER ROLE :"app_role" WITH PASSWORD :'app_pw';
ALTER ROLE :"app_role" SET statement_timeout = '15s';
ALTER ROLE :"app_role" SET idle_in_transaction_session_timeout = '30s';
SELECT format('REVOKE %I FROM %I', g.rolname, :'app_role')
FROM pg_auth_members m
JOIN pg_roles g ON g.oid = m.roleid
JOIN pg_roles u ON u.oid = m.member
WHERE u.rolname = :'app_role' \gexec

\unset app_pw
\unset mig_pw

-- 3. Template DB owned by the migrator. Default privileges are stored per
--    database, so every DB created from it (dev, test) inherits them.
SELECT format('CREATE DATABASE %I OWNER %I', :'tpl_db', :'mig_role')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'tpl_db') \gexec
REVOKE ALL ON DATABASE :"tpl_db" FROM PUBLIC;

\connect :tpl_db
ALTER SCHEMA public OWNER TO :"mig_role";
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"app_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"mig_role" IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"mig_role" IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO :"app_role";

-- 4. Dev DB from the template; database ACLs are not copied, so set them here.
\connect postgres
SELECT format('CREATE DATABASE %I OWNER %I TEMPLATE %I', :'dev_db', :'mig_role', :'tpl_db')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'dev_db') \gexec
REVOKE ALL ON DATABASE :"dev_db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"dev_db" TO :"app_role", :"mig_role";
SQL

echo "bootstrap: roles and databases are in place."
