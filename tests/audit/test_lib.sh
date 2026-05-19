#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

t::run "passes a true assertion" '
  t::assert "1 equals 1" "[ 1 = 1 ]"
'

t::run "fails a false assertion" '
  if t::assert "1 equals 2" "[ 1 = 2 ]" 2>/dev/null; then
    echo "expected failure but assertion passed" >&2
    return 1
  fi
'

t::summary
