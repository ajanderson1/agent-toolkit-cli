#!/usr/bin/env bash
# audit/demos/skill-claude.sh — reference cell for skill × claude.
#
# Self-hosting: outside tmux, spawns a session and prints the attach
# command; inside tmux, runs the narrated demo and exits with the
# accumulated assertion status.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"

if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-skill-claude"
  tmux kill-session -t "$session" 2>/dev/null || true
  tmux new-session -d -s "$session" "AUDIT_INSIDE_TMUX=1 bash $SCRIPT_PATH"
  printf 'tmux attach -t %s\n' "$session"
  exit 0
fi

# --- inside tmux ---
source "$REPO_ROOT/audit/lib/sandbox.sh"
source "$REPO_ROOT/audit/lib/narrate.sh"
source "$REPO_ROOT/audit/lib/assert.sh"
sandbox::init

step "skill × claude — smoke check (skeleton)"
run "echo HOME=$HOME"
run "echo AGENT_TOOLKIT_REPO=$AGENT_TOOLKIT_REPO"

# Smoke: a fresh sandbox HOME is a real directory and AGENT_TOOLKIT_REPO
# points at something with a skills/ folder.
assert_exit_code 0 -- test -d "$HOME"
assert_exit_code 0 -- test -d "$AGENT_TOOLKIT_REPO/skills"

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
