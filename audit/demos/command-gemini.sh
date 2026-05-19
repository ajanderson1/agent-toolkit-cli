#!/usr/bin/env bash
# audit/demos/command-gemini.sh — audit cell for command × gemini.
#
# FINDING: demo-command does not declare 'gemini' in its harnesses list
# (declares: claude, opencode).  The CLI correctly rejects the
# link with exit code 1 and the message:
#
#   "command:demo-command doesn't support harness 'gemini' (declares: claude,
#    opencode). Use a different harness or pick another asset."
#
# Root cause: no command in the agent-toolkit repo currently declares 'gemini'
# as a supported harness.  The CLI infrastructure IS in place — 'gemini' is
# listed in ALL_HARNESSES, (gemini, command) maps to ~/.gemini/commands, and
# the projection logic uses raw symlinks for (gemini, command) — but the asset
# metadata doesn't authorise any command for the gemini harness.
#
# The T11 empirical-matrix probe recorded supported=true (code_probe) because
# the harness + kind combination has a registered target path, but the probe
# couldn't find a materialised symlink because the link is always rejected
# before projection.  That disagreement is now explained.
#
# The asserts below test the EXPECTED behavior (link succeeds, symlink
# appears).  They will FAIL until a command declares harness: gemini, surfacing
# this gap in audit/.last-run.tsv and [FAIL] in the generated doc cell.
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

# Projection shape for (gemini, command) — per _support.py:
#   User target:    ~/.gemini/commands/<slug>   (raw symlink)
#   Project target: .gemini/commands/<slug>     (raw symlink)
#
# FINDING: link user gemini command:demo-command exits 1 because demo-command
# does not declare 'gemini' in its harnesses list.  The expected path below
# will never be created under current asset metadata.

TARGET="$HOME/.gemini/commands/demo-command.md"
EXPECTED_TARGET="$AGENT_TOOLKIT_REPO/commands/demo-command.md"
ALLOWLIST="$HOME/.agent-toolkit.yaml"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user gemini command:demo-command"
# Expected: exits 0, creates symlink at ~/.gemini/commands/demo-command.md.
# Observed: exits 1 — demo-command doesn't declare harness 'gemini'.
# The assert_exit_code below records the FINDING as a visible FAIL.
run "agent-toolkit-cli link user gemini command:demo-command || true"
assert_exit_code 0 -- agent-toolkit-cli link user gemini command:demo-command
# Downstream symlink asserts will also fail, amplifying the finding signal.
assert_symlink_exists "$TARGET"
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"
assert_file_contains  "$ALLOWLIST" "demo-command"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
# Also expected to fail for the same reason.
assert_exit_code 0 -- agent-toolkit-cli link user gemini command:demo-command
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"
pause 1

step "Lifecycle 3/4 — unlink user gemini command:demo-command"
run "agent-toolkit-cli unlink user gemini command:demo-command || true"
assert_no_symlink "$TARGET"
pause 1

step "Lifecycle 4/4 — project-scope link"
mkdir -p "$HOME/proj" && cd "$HOME/proj"
git init -q
run "agent-toolkit-cli --project . link project gemini command:demo-command || true"
assert_exit_code 0 -- agent-toolkit-cli --project . link project gemini command:demo-command
# Also fails for the same reason.
assert_exit_code 0 -- test -e ".gemini/commands/demo-command.md"
cd - >/dev/null

# ---------- Validation ----------
step "Validation 1/2 — doctor runs without hard failure"
# doctor exits 0 by default; the sandbox has nothing linked so symlink-integrity
# group warns for all unlinked assets — expected and documented.
run "agent-toolkit-cli doctor"
assert_exit_code 0 -- agent-toolkit-cli doctor

step "Validation 2/2 — list command gemini"
# list should exit 0 even when nothing is linked.
run "agent-toolkit-cli list command gemini || true"
assert_exit_code 0 -- agent-toolkit-cli list command gemini

# ---------- Inspection ----------
step "Inspection — diff user gemini"
run "agent-toolkit-cli diff user gemini || true"

# ---------- Finding summary ----------
step "Finding — no command declares harness: gemini"
# Confirm the rejection is caused by missing frontmatter, not a CLI crash.
# The CLI emits a clear message; we record the finding as a named assertion.
gemini_out=""
gemini_rc=0
gemini_out=$(agent-toolkit-cli link user gemini command:demo-command 2>&1) || gemini_rc=$?
if echo "$gemini_out" | grep -q "doesn't support harness 'gemini'"; then
  _assert_record 1 "FINDING CONFIRMED: link rejects command:demo-command with 'doesn't support harness gemini' (rc=$gemini_rc)"
else
  _assert_record 0 "FINDING: unexpected link output — $gemini_out"
fi

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
