#!/usr/bin/env bash
# Assertions on the running compose `db` service (SC-23, NT3-22, NT3-23).
#   1. The published port is bound to loopback only.
#   2. A TCP login as the app role with a wrong password is rejected.
#   3. Re-running bootstrap succeeds and leaves role attributes, memberships,
#      database/schema ACLs and default privileges unchanged.
# Prints no secret: it never reads the env file; the container already holds
# the variables it needs.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
dc=(docker compose)

port="$("${dc[@]}" port db 5432)"
if [[ "$port" != 127.0.0.1:* ]]; then
  echo "db-check: port 5432 is not bound to 127.0.0.1 only" >&2
  exit 1
fi
echo "db-check: port bound to loopback"

# The wrong password is a fixed non-secret literal; the role name comes from
# the container environment (expanded by sh inside the container).
# shellcheck disable=SC2016
if "${dc[@]}" exec -T -e PGPASSWORD=wrong-password-for-check -e PGCONNECT_TIMEOUT=5 db \
  sh -c 'psql -X -h 127.0.0.1 -U "$DB_APP_USER" -d "$DB_NAME" -c "SELECT 1"' >/dev/null 2>&1; then
  echo "db-check: login with a wrong password succeeded" >&2
  exit 1
fi
echo "db-check: wrong-password TCP login rejected"

# The $VARS below are expanded by sh inside the container (which holds them),
# not by this script; names reach SQL only as psql variables (:'name').
# shellcheck disable=SC2016
snapshot() {
  "${dc[@]}" exec -T db sh -c \
    'psql -X -At -U postgres -d postgres -v app="$DB_APP_USER" -v mig="$DB_MIGRATOR_USER" -f -' <<'SQL'
SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin,
       rolreplication, rolbypassrls, rolconfig
FROM pg_roles WHERE rolname IN (:'app', :'mig') ORDER BY rolname;
SELECT r.rolname, m.rolname FROM pg_auth_members a
JOIN pg_roles r ON r.oid = a.roleid JOIN pg_roles m ON m.oid = a.member ORDER BY 1, 2;
SELECT datname, pg_get_userbyid(datdba), datacl FROM pg_database ORDER BY datname;
SQL
  for db_var in DB_NAME TEMPLATE_DB; do
    "${dc[@]}" exec -T -e TEMPLATE_DB=rms_template db sh -c \
      "psql -X -At -U postgres -d \"\$${db_var}\" -f -" <<'SQL'
SELECT nspname, pg_get_userbyid(nspowner), nspacl FROM pg_namespace WHERE nspname = 'public';
SELECT pg_get_userbyid(defaclrole), defaclobjtype, defaclacl FROM pg_default_acl ORDER BY 1, 2;
SQL
  done
}

before="$(snapshot)"
"${dc[@]}" exec -T db /docker-entrypoint-initdb.d/10-bootstrap.sh >/dev/null
after="$(snapshot)"
if [[ "$before" != "$after" ]]; then
  echo "db-check: re-running bootstrap changed roles or grants" >&2
  diff <(echo "$before") <(echo "$after") >&2 || true
  exit 1
fi
echo "db-check: bootstrap re-run is idempotent"
