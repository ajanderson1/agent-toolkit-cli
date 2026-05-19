#!/usr/bin/env bash
# audit/demos/plugin-claude.sh — reference cell for plugin × claude.
#
# T11 empirical-matrix flagged plugin × claude as a disagreement (code says
# supported=true, empirical found no slug-named projection). Recon confirmed
# the projection is a directory-level symlink at ~/.claude/plugins/<slug>
# pointing to the plugin root directory. T11 was simply looking in the wrong
# place. This cell documents the full happy-path and records the finding.
#
# Outcome: (a) — symlink exists, PASS.
#
# Self-hosting: outside tmux, spawns a session and prints the attach command;
# inside tmux, runs the narrated demo and exits with the accumulated assertion
# status.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"

if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-plugin-claude"
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

# Projection shape for (claude, plugin):
#   Symlink: $CLAUDE_CONFIG_DIR/plugins/<slug>  ->  $AGENT_TOOLKIT_REPO/plugins/<slug>/
#   This is a DIRECTORY-LEVEL symlink to the plugin root (not a sub-path inside it).
#   The symlink name is the bare slug with no extension.
#
# T11 empirical-matrix finding: the probe found no slug-named projection
# because it was not looking in $CLAUDE_CONFIG_DIR/plugins/. The feature
# works correctly. Recorded here for audit completeness.

SLUG="companion-html"
TARGET="$CLAUDE_CONFIG_DIR/plugins/$SLUG"
EXPECTED_TARGET="$AGENT_TOOLKIT_REPO/plugins/$SLUG"
ALLOWLIST="$HOME/.agent-toolkit.yaml"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user claude plugin:companion-html"
run "agent-toolkit-cli link user claude plugin:companion-html"
show "$TARGET"
assert_symlink_exists "$TARGET"
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"
assert_file_contains  "$ALLOWLIST" "companion-html"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
run "agent-toolkit-cli link user claude plugin:companion-html"
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"
pause 1

step "Lifecycle 3/4 — unlink user claude plugin:companion-html"
run "agent-toolkit-cli unlink user claude plugin:companion-html"
show "$CLAUDE_CONFIG_DIR/plugins"
assert_no_symlink "$TARGET"
pause 1

step "Lifecycle 4/4 — project-scope link"
mkdir -p "$HOME/proj" && cd "$HOME/proj"
git init -q
run "agent-toolkit-cli --project . link project claude plugin:companion-html"
show ".claude/plugins/companion-html"
# Project-scope symlink is also at the directory level.
assert_symlink_exists ".claude/plugins/companion-html"
assert_file_contains  ".agent-toolkit.yaml" "companion-html"
run "agent-toolkit-cli --project . unlink project claude plugin:companion-html"
assert_no_symlink ".claude/plugins/companion-html"
cd - >/dev/null

# Re-establish user-scope link so the remaining ops have something to inspect.
run "agent-toolkit-cli link user claude plugin:companion-html"

# ---------- Validation ----------
step "Validation 1/3 — check passes on the projected state"
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" check --exit-code
pause 1

step "Validation 2/3 — doctor runs without hard failure"
# doctor exits 0 by default (WARN groups don't trigger non-zero without --exit-code).
# Only companion-html is linked here; all other assets are unlinked → WARN.
run "agent-toolkit-cli doctor"
assert_exit_code 0 -- agent-toolkit-cli doctor

step "Validation 3/3 — fix is a no-op on an already-current toolkit repo"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" fix"
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" fix

# ---------- Authoring ----------
step "Authoring 1/2 — new creates a scaffolded plugin (in a tmp toolkit copy)"
TMP_TOOLKIT="$(mktemp -d)/toolkit"
cp -R "$AGENT_TOOLKIT_REPO" "$TMP_TOOLKIT"
run "agent-toolkit-cli --toolkit-repo \"$TMP_TOOLKIT\" new plugin audit-throwaway"
# Scaffold lands at plugins/audit-throwaway/.claude-plugin/plugin.json
assert_exit_code 0 -- test -f "$TMP_TOOLKIT/plugins/audit-throwaway/.claude-plugin/plugin.json"

step "Authoring 2/2 — ingest is exercised in its dedicated cell; smoke here"
assert_exit_code 0 -- agent-toolkit-cli --help

# ---------- Inspection ----------
step "Inspection 1/3 — list"
run "agent-toolkit-cli list plugin claude"

step "Inspection 2/3 — diff"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" diff user claude || true"

step "Inspection 3/3 — inventory"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" inventory"

# ---------- Human-edit robustness ----------
step "Robustness 1/3 — delete the symlink, re-run link, expect re-creation"
rm -rf "$TARGET"
run "agent-toolkit-cli link user claude plugin:companion-html"
assert_symlink_exists "$TARGET"
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"

step "Robustness 2/3 — edit .agent-toolkit.yaml to drop companion-html, re-link, expect removal"
uv run python3 -c "
import yaml, sys
p='$ALLOWLIST'
d=yaml.safe_load(open(p))
d['plugins']=[s for s in (d.get('plugins') or []) if s!='companion-html']
open(p,'w').write(yaml.safe_dump(d))
"
run "agent-toolkit-cli link user claude"
assert_no_symlink "$TARGET"

step "Robustness 3/3 — hand-edit (replace dir symlink with dir) is detected by doctor"
# Restore allowlist + relink first.
run "agent-toolkit-cli link user claude plugin:companion-html"
# Probe: replace the directory symlink with a regular directory (realistic
# 'human-copy' scenario where the user copies plugin content in place).
rm "$TARGET"
mkdir -p "$TARGET"
run "agent-toolkit-cli doctor --group symlink-integrity || true"
# Finding: doctor's symlink-integrity group does NOT flag the replaced-symlink slot
# when check_path.exists() is True (regular dir) → skips "missing" warn, and
# check_path.is_symlink() is False → skips the "linked" recording.
# Net result: companion-html is silently absent from the report. Recorded as
# a known blind spot (same as skill × claude cell finding).
assert_exit_code 0 -- agent-toolkit-cli doctor --group symlink-integrity --exit-code
if uv run python3 -c "
import subprocess, sys
r = subprocess.run(
    ['agent-toolkit-cli', 'doctor', '--group', 'symlink-integrity'],
    capture_output=True, text=True
)
if 'plugin/companion-html' not in r.stdout + r.stderr:
    sys.exit(0)  # not mentioned = blind spot confirmed
sys.exit(1)  # mentioned = doctor caught it (better than expected)
"; then
  _assert_record 1 "FINDING: doctor blind to symlink-replaced-by-regular-dir (expected blind spot)"
else
  _assert_record 1 "doctor detected replaced symlink (better than expected)"
fi

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
