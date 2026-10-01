#!/usr/bin/env bash
# Create the local env file from the committed example, replacing every
# `change-me` placeholder with a random value (SC-26).
#
# - CSPRNG only (openssl rand); alphabet [0-9a-f], a subset of [A-Za-z0-9], so
#   values survive compose `$` interpolation and --env-file parsing.
# - DJANGO_SECRET_KEY: 96 characters; every other secret: 48 characters.
# - Never prints a value. Never overwrites an existing env file.
# - Written with umask 077 to a temp file in the same directory, then moved
#   into place with `mv -n`; final mode 0600.
#
# Paths can be overridden for tests: RMS_ENV_EXAMPLE, RMS_ENV_FILE.
set -euo pipefail
umask 077

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
example="${RMS_ENV_EXAMPLE:-$root/.env.example}"
target="${RMS_ENV_FILE:-$root/.env}"
placeholder="change-me"

if [[ -e "$target" ]]; then
  echo "init-env: env file already exists; left unchanged."
  exit 0
fi
if [[ ! -f "$example" ]]; then
  echo "init-env: env example not found." >&2
  exit 1
fi
command -v openssl >/dev/null || { echo "init-env: openssl is required." >&2; exit 1; }

tmp="$(mktemp "$(dirname "$target")/.init-env.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

keys_of() { grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' "$1" | sort; }

while IFS= read -r line || [[ -n "$line" ]]; do
  if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] && [[ "${BASH_REMATCH[2]}" == "$placeholder" ]]; then
    key="${BASH_REMATCH[1]}"
    if [[ "$key" == "DJANGO_SECRET_KEY" ]]; then
      value="$(openssl rand -hex 48)"
    else
      value="$(openssl rand -hex 24)"
    fi
    printf '%s=%s\n' "$key" "$value" >>"$tmp"
  else
    printf '%s\n' "$line" >>"$tmp"
  fi
done <"$example"

if grep -q -- "$placeholder" "$tmp"; then
  echo "init-env: a placeholder was left in the generated file; aborting." >&2
  exit 1
fi
if [[ "$(keys_of "$example")" != "$(keys_of "$tmp")" ]]; then
  echo "init-env: generated keys differ from the example; aborting." >&2
  exit 1
fi

chmod 600 "$tmp"
mv -n "$tmp" "$target" || true
if [[ -e "$tmp" ]]; then
  echo "init-env: env file appeared while generating; left unchanged."
  exit 0
fi
trap - EXIT
echo "init-env: created the env file with random secrets (mode 0600)."
