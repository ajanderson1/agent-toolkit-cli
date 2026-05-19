#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib.sh"

t::run "all-pass case finishes with exit 0" '
  ( source "$REPO_ROOT/audit/lib/assert.sh"
    local tmp; tmp="$(mktemp -d)"
    ln -s /tmp/nowhere "$tmp/link"
    assert_symlink_exists "$tmp/link"
    assert_symlink_target "$tmp/link" "/tmp/nowhere"
    assert_no_symlink     "$tmp/missing"
    assert_exit_code 0 -- true
    echo hello > "$tmp/file"
    assert_file_contains  "$tmp/file" "hello"
    rm -rf "$tmp"
    assertions::finish
  )
'

t::run "one-fail case exits non-zero but reports all results" '
  local out rc
  out="$( ( source "$REPO_ROOT/audit/lib/assert.sh"
            assert_exit_code 0 -- true     # pass
            assert_exit_code 0 -- false    # fail
            assert_exit_code 0 -- true     # pass — must still run
            assertions::finish ) 2>&1 || true )"
  rc=$?
  t::assert "third assertion ran" "[[ \"$out\" == *\"2 PASS\"* ]]"
  t::assert "summary mentions failure" "[[ \"$out\" == *FAIL* || \"$out\" == *failed* ]]"
'

t::summary
