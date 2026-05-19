#!/usr/bin/env bash
# audit/demos/command-gemini.sh — reference cell for command × gemini.
#
# demo-command now declares harness: gemini (alongside claude, opencode).
# This cell exercises the green-path lifecycle on the gemini target shape.
#
# Self-hosting: outside tmux, spawns a session and prints the attach
# command; inside tmux, runs the narrated demo and exits with the
# accumulated assertion status.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"

if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-command-gemini"
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

# Projection shape for (gemini, command) — translated cell:
#   User target:    ~/.gemini/commands/<slug>.toml   (symlink → cache)
#   Project target: .gemini/commands/<slug>.toml     (symlink → cache)
# The cache lives under ~/.gemini/.agent-toolkit-cache/command/<slug>.toml
# (project scope: .gemini/.agent-toolkit-cache/command/<slug>.toml).

TARGET="$HOME/.gemini/commands/demo-command.toml"
EXPECTED_TARGET="$HOME/.gemini/.agent-toolkit-cache/command/demo-command.toml"
ALLOWLIST="$HOME/.agent-toolkit.yaml"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user gemini command:demo-command"
run "agent-toolkit-cli link user gemini command:demo-command"
assert_exit_code 0 -- agent-toolkit-cli link user gemini command:demo-command
assert_symlink_exists "$TARGET"
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"
assert_file_contains  "$ALLOWLIST" "demo-command"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
assert_exit_code 0 -- agent-toolkit-cli link user gemini command:demo-command
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"
pause 1

step "Lifecycle 3/4 — unlink user gemini command:demo-command"
run "agent-toolkit-cli unlink user gemini command:demo-command"
assert_no_symlink "$TARGET"
pause 1

step "Lifecycle 4/4 — project-scope link"
mkdir -p "$HOME/proj" && cd "$HOME/proj"
PROJ_REAL="$(pwd -P)"
git init -q
run "agent-toolkit-cli --project . link project gemini command:demo-command"
assert_exit_code 0 -- agent-toolkit-cli --project . link project gemini command:demo-command
assert_symlink_exists ".gemini/commands/demo-command.toml"
assert_symlink_target ".gemini/commands/demo-command.toml" "$PROJ_REAL/.gemini/.agent-toolkit-cache/command/demo-command.toml"
cd - >/dev/null

# ---------- Validation ----------
step "Validation 1/2 — doctor runs without hard failure"
run "agent-toolkit-cli doctor"
assert_exit_code 0 -- agent-toolkit-cli doctor

step "Validation 2/2 — list command gemini"
run "agent-toolkit-cli list command gemini || true"
assert_exit_code 0 -- agent-toolkit-cli list command gemini

# ---------- Inspection ----------
step "Inspection — diff user gemini"
run "agent-toolkit-cli diff user gemini || true"

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
