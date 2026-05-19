# audit/lib/assert.sh — accumulating assertions for audit demo scripts.
#
# Each helper records a pass/fail line. `assertions::finish` prints a
# summary and exits non-zero if any assertion failed.

ASSERT_PASS=0
ASSERT_FAIL=0
ASSERT_LOG=""

_assert_record() {
  local ok="$1" desc="$2"
  if [ "$ok" = "1" ]; then
    ASSERT_PASS=$((ASSERT_PASS + 1))
    ASSERT_LOG="${ASSERT_LOG}PASS  ${desc}
"
  else
    ASSERT_FAIL=$((ASSERT_FAIL + 1))
    ASSERT_LOG="${ASSERT_LOG}FAIL  ${desc}
"
  fi
}

assert_symlink_exists() {
  local path="$1"
  if [ -L "$path" ]; then _assert_record 1 "symlink exists: $path"
  else                    _assert_record 0 "symlink exists: $path"
  fi
}

assert_no_symlink() {
  local path="$1"
  if [ -L "$path" ] || [ -e "$path" ]; then _assert_record 0 "no symlink at: $path"
  else                                       _assert_record 1 "no symlink at: $path"
  fi
}

assert_symlink_target() {
  local path="$1" expected="$2" actual=""
  if [ -L "$path" ]; then actual="$(readlink "$path")"; fi
  if [ "$actual" = "$expected" ]; then
    _assert_record 1 "symlink $path -> $expected"
  else
    _assert_record 0 "symlink $path -> $expected (got: $actual)"
  fi
}

assert_file_contains() {
  local path="$1" needle="$2"
  if [ -f "$path" ] && grep -qF -- "$needle" "$path"; then
    _assert_record 1 "file contains '$needle': $path"
  else
    _assert_record 0 "file contains '$needle': $path"
  fi
}

# assert_exit_code EXPECTED -- cmd [args...]
assert_exit_code() {
  local expected="$1"; shift
  if [ "$1" != "--" ]; then
    _assert_record 0 "assert_exit_code: missing '--' separator"
    return
  fi
  shift
  local rc=0
  "$@" >/dev/null 2>&1 || rc=$?
  if [ "$rc" = "$expected" ]; then
    _assert_record 1 "exit $expected: $*"
  else
    _assert_record 0 "exit $expected: $* (got: $rc)"
  fi
}

assertions::finish() {
  printf '\n%s' "$ASSERT_LOG"
  printf '\n%d PASS · %d FAIL\n' "$ASSERT_PASS" "$ASSERT_FAIL"
  [ "$ASSERT_FAIL" -eq 0 ]
}
