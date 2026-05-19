#!/usr/bin/env bash
# audit/demos/command-claude.sh — reference cell for command × claude.
#
# Self-hosting: outside tmux, spawns a session and prints the attach
# command; inside tmux, runs the narrated demo and exits with the
# accumulated assertion status.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"

if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-command-claude"
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

# Projection shape for (claude, command):
#   Symlink: $CLAUDE_CONFIG_DIR/commands/<slug>.md  ->  $AGENT_TOOLKIT_REPO/commands/<slug>.md
#   This is a FILE-LEVEL symlink (includes the .md suffix).
#   The symlink name is the slug with .md extension appended.

LINK_PATH="$CLAUDE_CONFIG_DIR/commands/demo-command.md"
EXPECTED_TARGET="$AGENT_TOOLKIT_REPO/commands/demo-command.md"
ALLOWLIST="$HOME/.agent-toolkit.yaml"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user claude command:demo-command"
run "agent-toolkit-cli link user claude command:demo-command"
show "$CLAUDE_CONFIG_DIR/commands"
assert_symlink_exists "$LINK_PATH"
assert_symlink_target "$LINK_PATH" "$EXPECTED_TARGET"
assert_file_contains  "$ALLOWLIST" "demo-command"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
run "agent-toolkit-cli link user claude command:demo-command"
assert_symlink_target "$LINK_PATH" "$EXPECTED_TARGET"
pause 1

step "Lifecycle 3/4 — unlink user claude command:demo-command"
# BUG: unlink is a no-op for commands — the symlink is NOT removed.
# Expected: symlink removed. Actual: symlink remains, exit 0, "nothing to change".
run "agent-toolkit-cli unlink user claude command:demo-command"
show "$CLAUDE_CONFIG_DIR/commands"
# This assert FAILS — documenting the known bug.
assert_no_symlink "$LINK_PATH"
pause 1

step "Lifecycle 4/4 — project-scope link"
mkdir -p "$HOME/proj" && cd "$HOME/proj"
git init -q
run "agent-toolkit-cli --project . link project claude command:demo-command"
show ".claude/commands/demo-command.md"
# Project-scope symlink is also a file-level symlink with .md suffix.
assert_symlink_exists ".claude/commands/demo-command.md"
assert_file_contains  ".agent-toolkit.yaml" "demo-command"
run "agent-toolkit-cli --project . unlink project claude command:demo-command"
# BUG: same unlink no-op applies at project scope.
assert_no_symlink ".claude/commands/demo-command.md"
cd - >/dev/null

# Re-establish user-scope link so the remaining ops have something to inspect.
run "agent-toolkit-cli link user claude command:demo-command"

# ---------- Validation ----------
step "Validation 1/3 — check passes on the projected state"
# check validates asset frontmatter + AGENTS.md regions; exits 0 when all is OK.
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" check --exit-code
pause 1

step "Validation 2/3 — doctor runs without hard failure"
# doctor exits 0 by default (WARN groups don't trigger non-zero without --exit-code).
# In the sandbox we have only demo-command linked, so symlink-integrity will WARN
# for all the unlinked assets — that is expected and documented as a finding.
run "agent-toolkit-cli doctor"
assert_exit_code 0 -- agent-toolkit-cli doctor

step "Validation 3/3 — fix is a no-op on an already-current toolkit repo"
# fix regenerates AGENTS.md auto-regions; exits 0 whether or not it wrote changes.
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" fix"
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" fix

# ---------- Authoring ----------
step "Authoring 1/2 — new creates a scaffolded command (in a tmp toolkit copy)"
TMP_TOOLKIT="$(mktemp -d)/toolkit"
cp -R "$AGENT_TOOLKIT_REPO" "$TMP_TOOLKIT"
run "agent-toolkit-cli --toolkit-repo \"$TMP_TOOLKIT\" new command audit-throwaway"
# Commands are single .md files, not directories.
assert_exit_code 0 -- test -f "$TMP_TOOLKIT/commands/audit-throwaway.md"

step "Authoring 2/2 — ingest is exercised in its dedicated cell; smoke here"
assert_exit_code 0 -- agent-toolkit-cli --help

# ---------- Inspection ----------
step "Inspection 1/3 — list"
# Correct invocation: list [KIND] [HARNESS]  (not list SCOPE HARNESS)
run "agent-toolkit-cli list command claude"

step "Inspection 2/3 — diff"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" diff user claude || true"

step "Inspection 3/3 — inventory"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" inventory"

# ---------- Human-edit robustness ----------
step "Robustness 1/3 — delete the symlink, re-run link, expect re-creation"
rm -f "$LINK_PATH"
run "agent-toolkit-cli link user claude command:demo-command"
assert_symlink_exists "$LINK_PATH"
assert_symlink_target "$LINK_PATH" "$EXPECTED_TARGET"

step "Robustness 2/3 — edit .agent-toolkit.yaml to drop demo-command, re-link, expect removal"
# Use uv run python3 so PyYAML is available (not always in system python).
uv run python3 -c "
import yaml, sys
p='$ALLOWLIST'
d=yaml.safe_load(open(p))
d['commands']=[s for s in (d.get('commands') or []) if s!='demo-command']
open(p,'w').write(yaml.safe_dump(d))
"
run "agent-toolkit-cli link user claude"
# BUG: stale symlinks are NOT pruned on reconcile — the symlink remains even
# though demo-command was removed from the allowlist.
# Expected: symlink removed. Actual: symlink remains ("already in sync").
assert_no_symlink "$LINK_PATH"

step "Robustness 3/3 — hand-edit the projected file is detected by doctor"
# Restore allowlist + relink first.
run "agent-toolkit-cli link user claude command:demo-command"
# Probe: replace the file symlink with a regular file (a realistic
# 'human-edit' scenario where the user copies content in place).
rm "$LINK_PATH"
echo "hand-edited" > "$LINK_PATH"
run "agent-toolkit-cli doctor --group symlink-integrity || true"
# Since #129, doctor's symlink-integrity group correctly flags a slot whose
# symlink has been replaced by a regular file and exits non-zero under
# --exit-code. The earlier blind-spot behavior is gone.
assert_exit_code 1 -- agent-toolkit-cli doctor --group symlink-integrity --exit-code
_assert_record 1 "doctor detected replaced symlink (post-#129 behavior)"

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
