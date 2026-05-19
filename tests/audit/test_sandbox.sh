#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=/dev/null
source "$REPO_ROOT/audit/lib/sandbox.sh"

t::run "init sets HOME under a tmpdir and exports harness vars" '
  sandbox::init
  t::assert "HOME is set"            "[ -n \"\$HOME\" ]"
  t::assert "HOME is a directory"    "[ -d \"\$HOME\" ]"
  t::assert "HOME prefix is tmpdir"  "[[ \"\$HOME\" == */agent-toolkit-audit.* ]]"
  t::assert "CLAUDE_CONFIG_DIR set"  "[ -n \"\${CLAUDE_CONFIG_DIR:-}\" ]"
  t::assert "CODEX_HOME set"         "[ -n \"\${CODEX_HOME:-}\" ]"
  t::assert "XDG_CONFIG_HOME set"    "[ -n \"\${XDG_CONFIG_HOME:-}\" ]"
  t::assert "AGENT_TOOLKIT_REPO set" "[ -n \"\${AGENT_TOOLKIT_REPO:-}\" ]"
  t::assert "toolkit repo exists"    "[ -d \"\$AGENT_TOOLKIT_REPO\" ]"
'

t::run "cleanup removes the tmpdir" '
  sandbox::init
  local h="$HOME"
  sandbox::cleanup
  t::assert "tmpdir removed" "[ ! -d \"$h\" ]"
'

t::summary
