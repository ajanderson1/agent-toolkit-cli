# tests/audit/lib.sh — minimal pure-bash test runner.
# Sourced by every audit shell test. Tracks pass/fail counts; `t::summary`
# exits non-zero if any test failed.

T_PASS=0
T_FAIL=0
T_CURRENT=""

t::run() {
  local name="$1" body="$2"
  T_CURRENT="$name"
  if ( eval "$body" ); then
    printf '  ok  %s\n' "$name"
    T_PASS=$((T_PASS + 1))
  else
    printf '  FAIL %s\n' "$name" >&2
    T_FAIL=$((T_FAIL + 1))
  fi
  T_CURRENT=""
}

# Note: calling t::assert outside a t::run body means a failing assert returns 1,
# which under set -euo pipefail will abort the sourcing script silently.
t::assert() {
  local msg="$1" cond="$2"
  if eval "$cond"; then
    return 0
  fi
  if [ -n "$T_CURRENT" ]; then
    printf '    [%s] assert failed: %s (cond: %s)\n' "$T_CURRENT" "$msg" "$cond" >&2
  else
    printf '    assert failed: %s (cond: %s)\n' "$msg" "$cond" >&2
  fi
  return 1
}

t::summary() {
  printf '\n%d passed, %d failed\n' "$T_PASS" "$T_FAIL"
  [ "$T_FAIL" -eq 0 ]
}
