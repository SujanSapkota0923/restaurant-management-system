#!/usr/bin/env bash
# Self-test for check-workflows.sh (change 0003, security review F2/F3).
# Every fixture in scripts/ci/testdata/ holds exactly one policy fault, named
# on its first line as `# expect: <failure message>`. The policy script must
# exit 1 on each fixture, report that message, and report no other failure.
# The fixtures live outside .github/workflows/ so GitHub never runs them.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
check="$here/check-workflows.sh"
shopt -s nullglob
fixtures=("$here"/testdata/*.yml)
((${#fixtures[@]} > 0)) || { echo "test-check-workflows: no fixtures found" >&2; exit 1; }

status=0
bad() { echo "test-check-workflows: $1: $2" >&2; status=1; }

for fixture in "${fixtures[@]}"; do
  name="${fixture##*/}"
  expect="$(sed -n '1s/^# expect: //p' "$fixture")"
  if [[ -z "$expect" ]]; then
    bad "$name" "first line must be '# expect: <failure message>'"
    continue
  fi
  rc=0
  out="$("$check" "$fixture" 2>&1)" || rc=$?
  if ((rc != 1)); then
    bad "$name" "policy script exited $rc, expected 1"
  elif ! grep -qF -- "$expect" <<<"$out"; then
    bad "$name" "expected failure '$expect' was not reported"
  elif grep -E '^check-workflows: ' <<<"$out" | grep -qvF -- "$expect"; then
    bad "$name" "fixture also trips another rule (it must hold exactly one fault)"
  fi
done

if ((status == 0)); then
  echo "test-check-workflows: OK (${#fixtures[@]} fixtures rejected as expected)"
fi
exit "$status"
