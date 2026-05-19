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

# Projection shape for (claude, skill):
#   Symlink: $CLAUDE_CONFIG_DIR/skills/<slug>  ->  $AGENT_TOOLKIT_REPO/skills/<slug>/
#   This is a DIRECTORY-LEVEL symlink (not SKILL.md-level).
#   The symlink name is the bare slug with no extension.

LINK_DIR="$CLAUDE_CONFIG_DIR/skills/demo-skill"
# TARGET is the symlink path itself (the directory symlink).
TARGET="$CLAUDE_CONFIG_DIR/skills/demo-skill"
EXPECTED_TARGET="$AGENT_TOOLKIT_REPO/skills/demo-skill"
ALLOWLIST="$HOME/.agent-toolkit.yaml"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user claude skill:demo-skill"
run "agent-toolkit-cli link user claude skill:demo-skill"
show "$LINK_DIR"
assert_symlink_exists "$TARGET"
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"
assert_file_contains  "$ALLOWLIST" "demo-skill"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
run "agent-toolkit-cli link user claude skill:demo-skill"
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"
pause 1

step "Lifecycle 3/4 — unlink user claude skill:demo-skill"
run "agent-toolkit-cli unlink user claude skill:demo-skill"
show "$CLAUDE_CONFIG_DIR/skills"
assert_no_symlink "$TARGET"
pause 1

step "Lifecycle 4/4 — project-scope link"
mkdir -p "$HOME/proj" && cd "$HOME/proj"
git init -q
run "agent-toolkit-cli --project . link project claude skill:demo-skill"
show ".claude/skills/demo-skill"
# Project-scope symlink is also at the directory level (no /SKILL.md suffix).
assert_symlink_exists ".claude/skills/demo-skill"
assert_file_contains  ".agent-toolkit.yaml" "demo-skill"
run "agent-toolkit-cli --project . unlink project claude skill:demo-skill"
assert_no_symlink ".claude/skills/demo-skill"
cd - >/dev/null

# Re-establish user-scope link so the remaining ops have something to inspect.
run "agent-toolkit-cli link user claude skill:demo-skill"

# ---------- Validation ----------
step "Validation 1/3 — check passes on the projected state"
# check validates asset frontmatter + AGENTS.md regions; exits 0 when all is OK.
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" check --exit-code
pause 1

step "Validation 2/3 — doctor runs without hard failure"
# doctor exits 0 by default (WARN groups don't trigger non-zero without --exit-code).
# In the sandbox we have only demo-skill linked, so symlink-integrity will WARN
# for all the unlinked assets — that is expected and documented as a finding.
run "agent-toolkit-cli doctor"
assert_exit_code 0 -- agent-toolkit-cli doctor

step "Validation 3/3 — fix is a no-op on an already-current toolkit repo"
# fix regenerates AGENTS.md auto-regions; exits 0 whether or not it wrote changes.
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" fix"
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" fix

# ---------- Authoring ----------
step "Authoring 1/2 — new creates a scaffolded skill (in a tmp toolkit copy)"
TMP_TOOLKIT="$(mktemp -d)/toolkit"
cp -R "$AGENT_TOOLKIT_REPO" "$TMP_TOOLKIT"
run "agent-toolkit-cli --toolkit-repo \"$TMP_TOOLKIT\" new skill audit-throwaway"
assert_exit_code 0 -- test -f "$TMP_TOOLKIT/skills/audit-throwaway/SKILL.md"

step "Authoring 2/2 — ingest is exercised in its dedicated cell; smoke here"
assert_exit_code 0 -- agent-toolkit-cli --help

# ---------- Inspection ----------
step "Inspection 1/3 — list"
# Correct invocation: list [KIND] [HARNESS]  (not list SCOPE HARNESS)
run "agent-toolkit-cli list skill claude"

step "Inspection 2/3 — diff"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" diff user claude || true"

step "Inspection 3/3 — inventory"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" inventory"

# ---------- Human-edit robustness ----------
step "Robustness 1/3 — delete the symlink, re-run link, expect re-creation"
rm -f "$TARGET"
run "agent-toolkit-cli link user claude skill:demo-skill"
assert_symlink_exists "$TARGET"
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"

step "Robustness 2/3 — edit .agent-toolkit.yaml to drop demo-skill, re-link, expect removal"
# Use uv run python3 so PyYAML is available (not always in system python).
uv run python3 -c "
import yaml, sys
p='$ALLOWLIST'
d=yaml.safe_load(open(p))
d['skills']=[s for s in (d.get('skills') or []) if s!='demo-skill']
open(p,'w').write(yaml.safe_dump(d))
"
run "agent-toolkit-cli link user claude"
assert_no_symlink "$TARGET"

step "Robustness 3/3 — hand-edit the projected file is detected by doctor"
# Restore allowlist + relink first.
run "agent-toolkit-cli link user claude skill:demo-skill"
# Probe: replace the directory symlink with a regular file (a realistic
# 'human-edit' scenario where the user copies content in place).
rm "$TARGET"
echo "hand-edited" > "$TARGET"
run "agent-toolkit-cli doctor --group symlink-integrity || true"
# Findings:
# 1. doctor's symlink-integrity group does NOT flag the replaced-symlink slot:
#    - check_path.exists() is True (regular file) → skips "missing" warn
#    - check_path.is_symlink() is False → skips the "linked" recording
#    - net result: demo-skill is silently absent from the report
# 2. --exit-code only fires on FAIL status, not WARN status, so even the
#    162 other unlinked assets (all WARN) do not trigger a non-zero exit.
#    Both of these are bugs / blind spots in doctor; recorded here as findings.
assert_exit_code 0 -- agent-toolkit-cli doctor --group symlink-integrity --exit-code
# Confirm demo-skill is not mentioned (blind spot confirmed).
if uv run python3 -c "
import subprocess, sys
r = subprocess.run(
    ['agent-toolkit-cli', 'doctor', '--group', 'symlink-integrity'],
    capture_output=True, text=True
)
if 'skill/demo-skill' not in r.stdout + r.stderr:
    sys.exit(0)  # not mentioned = blind spot confirmed
sys.exit(1)  # mentioned = doctor caught it (better than expected)
"; then
  _assert_record 1 "FINDING: doctor blind to symlink-replaced-by-regular-file (expected blind spot)"
else
  _assert_record 1 "doctor detected replaced symlink (better than expected)"
fi

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
