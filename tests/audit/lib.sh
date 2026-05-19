# tests/audit/lib.sh — minimal pure-bash test runner.
# Sourced by every audit shell test. Tracks pass/fail counts; `t::summary`
# exits non-zero if any test failed.

T_PASS=0
T_FAIL=0
T_CURRENT=""

t::run() {
  local name="$1" body="$2"
  T_CURRENT="$name"
  # Use a tmp file as a failure marker so t::assert failures propagate out of
  # the subshell even when the body's final command exits 0 (masking bug fix).
  local fail_marker; fail_marker="$(mktemp)"
  export T_FAIL_MARKER="$fail_marker"
  local rc=0
  ( eval "$body" ) || rc=$?
  local body_failed=0
  if [ -s "$fail_marker" ]; then body_failed=1; fi
  rm -f "$fail_marker"
  unset T_FAIL_MARKER
  if [ "$rc" -eq 0 ] && [ "$body_failed" -eq 0 ]; then
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
  # Signal failure to the enclosing t::run via the marker file (survives subshells).
  if [ -n "${T_FAIL_MARKER:-}" ]; then echo fail >> "$T_FAIL_MARKER"; fi
  return 1
}

t::summary() {
  printf '\n%d passed, %d failed\n' "$T_PASS" "$T_FAIL"
  [ "$T_FAIL" -eq 0 ]
}
