#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

t::run "passes a true assertion" '
  t::assert "1 equals 1" "[ 1 = 1 ]"
'

t::run "fails a false assertion" '
  # Isolate the inner assert from the outer t::run failure-tracking
  # by clearing T_FAIL_MARKER inside a subshell.
  local rc=0
  ( unset T_FAIL_MARKER; t::assert "1 equals 2" "[ 1 = 2 ]" 2>/dev/null ) || rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "expected failure but assertion passed" >&2
    return 1
  fi
'

t::summary
