#!/usr/bin/env bash
# audit/demos/agent-pi.sh — reference cell for agent × pi.
#
# Distinctive features exercised here:
#   - Dual-target projection: pi agent links materialise at BOTH the primary
#     path (~/.pi/agent/agents/<slug>) AND the alias path (~/.agents/<slug>).
#   - Project-scope asymmetry: project path is .pi/agents/ (no /agent/ infix),
#     while user-scope keeps the .pi/agent/ prefix.
#
# Self-hosting: outside tmux, spawns a session and prints the attach
# command; inside tmux, runs the narrated demo and exits with the
# accumulated assertion status.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"

if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-agent-pi"
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

# Projection shape for (pi, agent):
#   Primary symlink:  $HOME/.pi/agent/agents/demo-agent  ->  $AGENT_TOOLKIT_REPO/agents/demo-agent.md
#   Alias symlink:    $HOME/.agents/demo-agent            ->  $AGENT_TOOLKIT_REPO/agents/demo-agent.md
#
#   Both are FILE-LEVEL symlinks (pointing at the .md file directly).
#   The symlink name is the bare slug with no extension.
#   pi-subagents reads both locations; both are populated on every link call.

PRIMARY="$HOME/.pi/agent/agents/demo-agent"
ALIAS="$HOME/.agents/demo-agent"
EXPECTED_TARGET="$AGENT_TOOLKIT_REPO/agents/demo-agent.md"
ALLOWLIST="$HOME/.agent-toolkit.yaml"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user pi agent:demo-agent"
run "agent-toolkit-cli link user pi agent:demo-agent"
show "$HOME/.pi/agent/agents"
assert_symlink_exists "$PRIMARY"
assert_symlink_target "$PRIMARY" "$EXPECTED_TARGET"
# Alias path: pi-subagents reads ~/.agents/ in addition to ~/.pi/agent/agents/
assert_symlink_exists "$ALIAS"
assert_symlink_target "$ALIAS" "$EXPECTED_TARGET"
assert_file_contains  "$ALLOWLIST" "demo-agent"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
run "agent-toolkit-cli link user pi agent:demo-agent"
assert_symlink_target "$PRIMARY" "$EXPECTED_TARGET"
assert_symlink_target "$ALIAS"   "$EXPECTED_TARGET"
pause 1

step "Lifecycle 3/4 — unlink user pi agent:demo-agent"
run "agent-toolkit-cli unlink user pi agent:demo-agent"
show "$HOME/.pi/agent/agents"
assert_no_symlink "$PRIMARY"
# Alias must also be removed on unlink.
assert_no_symlink "$ALIAS"
pause 1

step "Lifecycle 4/4 — project-scope link"
# Project-scope path is .pi/agents/ (no /agent/ infix) — asymmetry with user scope.
mkdir -p "$HOME/proj" && cd "$HOME/proj"
git init -q
run "agent-toolkit-cli --project . link project pi agent:demo-agent"
show ".pi/agents"
assert_symlink_exists ".pi/agents/demo-agent"
# Project-scope alias at .agents/demo-agent.
assert_symlink_exists ".agents/demo-agent"
assert_file_contains  ".agent-toolkit.yaml" "demo-agent"
run "agent-toolkit-cli --project . unlink project pi agent:demo-agent"
assert_no_symlink ".pi/agents/demo-agent"
assert_no_symlink ".agents/demo-agent"
cd - >/dev/null

# Re-establish user-scope link so the remaining ops have something to inspect.
run "agent-toolkit-cli link user pi agent:demo-agent"

# ---------- Validation ----------
step "Validation 1/3 — check passes on the projected state"
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" check --exit-code
pause 1

step "Validation 2/3 — doctor runs without hard failure"
run "agent-toolkit-cli doctor"
assert_exit_code 0 -- agent-toolkit-cli doctor

step "Validation 3/3 — fix is a no-op on an already-current toolkit repo"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" fix"
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" fix

# ---------- Authoring ----------
step "Authoring 1/2 — new creates a scaffolded agent (in a tmp toolkit copy)"
TMP_TOOLKIT="$(mktemp -d)/toolkit"
cp -R "$AGENT_TOOLKIT_REPO" "$TMP_TOOLKIT"
run "agent-toolkit-cli --toolkit-repo \"$TMP_TOOLKIT\" new agent audit-throwaway"
assert_exit_code 0 -- test -f "$TMP_TOOLKIT/agents/audit-throwaway.md"

step "Authoring 2/2 — smoke: help exits 0"
assert_exit_code 0 -- agent-toolkit-cli --help

# ---------- Inspection ----------
step "Inspection 1/3 — list"
run "agent-toolkit-cli list agent pi"

step "Inspection 2/3 — diff"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" diff user pi || true"

step "Inspection 3/3 — inventory"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" inventory"

# ---------- Human-edit robustness ----------
step "Robustness 1/3 — delete the primary symlink, re-run link, expect re-creation"
rm -f "$PRIMARY"
run "agent-toolkit-cli link user pi agent:demo-agent"
assert_symlink_exists "$PRIMARY"
assert_symlink_target "$PRIMARY" "$EXPECTED_TARGET"
# Alias should still be intact.
assert_symlink_exists "$ALIAS"

step "Robustness 2/3 — edit .agent-toolkit.yaml to drop demo-agent, re-link, expect removal"
uv run python3 -c "
import yaml, sys
p='$ALLOWLIST'
d=yaml.safe_load(open(p))
d['agents']=[s for s in (d.get('agents') or []) if s!='demo-agent']
open(p,'w').write(yaml.safe_dump(d))
"
run "agent-toolkit-cli link user pi"
assert_no_symlink "$PRIMARY"
assert_no_symlink "$ALIAS"

step "Robustness 3/3 — hand-edit the projected file is detected by doctor (alias variant)"
# Restore allowlist + relink first.
run "agent-toolkit-cli link user pi agent:demo-agent"
# Replace the alias symlink with a regular file (realistic hand-edit scenario).
rm "$ALIAS"
echo "hand-edited" > "$ALIAS"
run "agent-toolkit-cli doctor --group symlink-integrity || true"
# Finding: doctor's symlink-integrity group does NOT flag the replaced-alias slot.
# check_path.exists() is True (regular file) → skips "missing" warn
# check_path.is_symlink() is False → skips the "linked" recording
# net result: demo-agent alias is silently absent from the report (blind spot).
assert_exit_code 0 -- agent-toolkit-cli doctor --group symlink-integrity --exit-code
if uv run python3 -c "
import subprocess, sys
r = subprocess.run(
    ['agent-toolkit-cli', 'doctor', '--group', 'symlink-integrity'],
    capture_output=True, text=True
)
# The alias path contains .agents/demo-agent; primary path contains .pi/agent/agents/demo-agent.
output = r.stdout + r.stderr
if 'agent/demo-agent' not in output and '.agents/demo-agent' not in output:
    sys.exit(0)  # not mentioned = blind spot confirmed
sys.exit(1)  # mentioned = doctor caught it (better than expected)
"; then
  _assert_record 1 "FINDING: doctor blind to alias symlink-replaced-by-regular-file (expected blind spot)"
else
  _assert_record 1 "doctor detected replaced alias symlink (better than expected)"
fi

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
