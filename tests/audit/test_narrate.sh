#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib.sh"
source "$REPO_ROOT/audit/lib/narrate.sh"

t::run "step prints the heading to stdout" '
  local out
  out="$(step "hello" 2>&1)"
  t::assert "heading appeared" "[[ \"$out\" == *hello* ]]"
'

t::run "run echoes then executes the command" '
  local out
  out="$(run "echo from-run" 2>&1)"
  t::assert "command echoed" "[[ \"$out\" == *echo\\ from-run* ]]"
  t::assert "command output appeared" "[[ \"$out\" == *from-run* ]]"
'

t::run "show on a missing path prints a clear marker" '
  local out
  out="$(show "/no/such/path" 2>&1)"
  t::assert "missing marker" "[[ \"$out\" == *MISSING* ]]"
'

t::run "pause respects PAUSE_SCALE=0" '
  local start end
  start=$(date +%s)
  PAUSE_SCALE=0 pause 5
  end=$(date +%s)
  t::assert "pause skipped" "[ $((end - start)) -lt 2 ]"
'

t::summary
