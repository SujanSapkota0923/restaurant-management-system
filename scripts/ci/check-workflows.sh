#!/usr/bin/env bash
# Workflow policy check (SC-30..SC-33, SC-37), complementing zizmor.
# Line-based on purpose: it is a tripwire, not a YAML parser. Usage:
#   scripts/ci/check-workflows.sh .github/workflows/*.yml
set -euo pipefail

(($# > 0)) || { echo "usage: $0 WORKFLOW..." >&2; exit 2; }
status=0
fail() { echo "check-workflows: $1: $2" >&2; status=1; }

for wf in "$@"; do
  # SC-30: forbidden triggers, in block form (key or list item) or on the
  # `on:` line itself (`on: name`, `on: [a, name]`, `on: {name: ...}`).
  for trigger in pull_request_target workflow_run issue_comment workflow_dispatch \
    repository_dispatch pull_request_review_comment; do
    if grep -qE "^[[:space:]]*-?[[:space:]]*${trigger}[[:space:]]*:?[[:space:]]*$|^[[:space:]]*${trigger}:|^on:.*(^|[^A-Za-z0-9_])${trigger}([^A-Za-z0-9_]|$)" "$wf"; then
      fail "$wf" "forbidden trigger '$trigger'"
    fi
  done

  # SC-31: read-only token, no secrets, no persisted credentials.
  if ! grep -qE '^permissions:[[:space:]]*$' "$wf" || ! grep -qE '^  contents: read[[:space:]]*$' "$wf"; then
    fail "$wf" "workflow-level 'permissions: contents: read' is missing"
  fi
  if grep -nE '^[[:space:]]+[a-z-]+:[[:space:]]*write' "$wf"; then
    fail "$wf" "a permission is raised to write"
  fi
  if grep -nE '^    permissions:' "$wf"; then
    fail "$wf" "a job sets its own permissions"
  fi
  if grep -nE 'secrets\.' "$wf" | grep -vE '^[0-9]+:[[:space:]]*#'; then
    fail "$wf" "references secrets.*"
  fi
  checkouts=$(grep -cE 'uses:[[:space:]]*actions/checkout@' "$wf" || true)
  persisted=$(grep -cE '^[[:space:]]+persist-credentials:[[:space:]]*false[[:space:]]*$' "$wf" || true)
  if [[ "$checkouts" != "$persisted" ]]; then
    fail "$wf" "every actions/checkout needs persist-credentials: false ($persisted of $checkouts)"
  fi

  # SC-32: every uses: pinned to a 40-hex SHA with a version comment.
  while IFS= read -r line; do
    if [[ ! "$line" =~ uses:[[:space:]]*[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}[[:space:]]+#[[:space:]]*v[0-9] ]]; then
      fail "$wf" "unpinned or uncommented action: ${line#"${line%%[![:space:]]*}"}"
    fi
  done < <(grep -E '^[[:space:]]*-?[[:space:]]*uses:' "$wf" || true)

  # SC-33: no expressions inside run: blocks (pass values through env:).
  awk '
    function indent(s) { match(s, /^ */); return RLENGTH }
    /^[[:space:]]*-?[[:space:]]*run:/ {
      in_run = 1; base = indent($0)
      if ($0 ~ /\$\{\{/) { print FILENAME ":" NR ": expression in run"; bad = 1 }
      next
    }
    in_run {
      if ($0 ~ /^[[:space:]]*$/) next
      if (indent($0) <= base) { in_run = 0 }
      else if ($0 ~ /\$\{\{/) { print FILENAME ":" NR ": expression in run"; bad = 1 }
    }
    END { exit bad }
  ' "$wf" >&2 || status=1

  # SC-37: no workspace artifacts, no env dumps, no interpolated compose config.
  # Env dump: a bare `env`, `printenv`, `set`, `export`, `declare`, `typeset`,
  # or `export -p`, `declare -p|-x`, `typeset -p`, `compgen -v|-e`, ending the
  # command (line end, `|`, `;`, `&`, `>` or `)`); `set -euo pipefail` passes.
  # Env-file read: a printing command whose arguments name a `.env` file
  # (`.env.example` passes; so does the mask step's redirect, which has no command).
  dump_re='(^|[[:space:];&|(])(env|printenv|set|export|declare|typeset|export -p|declare -[px]|typeset -p|compgen -[ve])[[:space:]]*($|[|;&>)])'
  read_re='(^|[[:space:];&|(])(cat|tac|nl|less|more|head|tail|bat|strings|base64|xxd|od)[[:space:]][^#]*\.env($|[^.A-Za-z0-9_-])'
  if grep -nE "actions/upload-artifact|${dump_re}|${read_re}|docker compose config|docker-compose config" "$wf"; then
    fail "$wf" "artifact upload, env dump or 'docker compose config' is not allowed"
  fi
done

if ((status == 0)); then
  echo "check-workflows: OK ($#)"
fi
exit "$status"
