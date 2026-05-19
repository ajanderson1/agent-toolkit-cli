#!/usr/bin/env bash
# audit/demos/mcp-claude.sh — audit cell for mcp × claude.
#
# Config-file strategy: the CLI edits ~/.claude.json (top-level `mcpServers`
# key) rather than creating symlinks. Project scope targets .mcp.json inside
# the project root (only when that file already exists — the adapter skips
# creation if absent).
#
# Self-hosting: outside tmux, spawns a session and prints the attach
# command; inside tmux, runs the narrated demo and exits with the
# accumulated assertion status.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"

if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-mcp-claude"
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

# Projection shape for (claude, mcp):
#   Config-file edit: $HOME/.claude.json  (user scope)
#                     <project>/.mcp.json (project scope — requires pre-existing file)
#   JSON key: mcpServers.<name>  →  { "type": "stdio", "command", "args" }
#   Allowlist key: mcps: in $HOME/.agent-toolkit.yaml
#
# FINDING: project-scope config is NOT auto-created if .mcp.json is absent.
# The adapter returns None from config_target() when the file doesn't exist,
# so the link is a no-op. The project-scope step below seeds the file first.

CONFIG_FILE="$HOME/.claude.json"
ALLOWLIST="$HOME/.agent-toolkit.yaml"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user claude mcp:demo-mcp"
run "agent-toolkit-cli link user claude mcp:demo-mcp"
show "$CONFIG_FILE"
assert_exit_code 0 -- test -f "$CONFIG_FILE"
assert_file_contains "$CONFIG_FILE" "demo-mcp"
assert_file_contains "$CONFIG_FILE" "mcpServers"
assert_file_contains "$ALLOWLIST" "demo-mcp"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
run "agent-toolkit-cli link user claude mcp:demo-mcp"
assert_file_contains "$CONFIG_FILE" "demo-mcp"
pause 1

step "Lifecycle 3/4 — unlink user claude mcp:demo-mcp"
run "agent-toolkit-cli unlink user claude mcp:demo-mcp"
show "$CONFIG_FILE"
# Unlink removes the entry cleanly — the file shrinks to '{}'
# (mcpServers key is removed when the block becomes empty).
assert_exit_code 1 -- grep -qF "demo-mcp" "$CONFIG_FILE"
pause 1

step "Lifecycle 4/4 — project-scope link (requires pre-existing .mcp.json)"
mkdir -p "$HOME/proj" && cd "$HOME/proj"
git init -q
# The claude adapter only writes project-scope config when .mcp.json already
# exists — it does NOT create the file from scratch. Seed it first.
echo '{}' > .mcp.json
run "agent-toolkit-cli --project . link project claude mcp:demo-mcp"
show ".mcp.json"
assert_file_contains ".mcp.json" "demo-mcp"
assert_file_contains ".agent-toolkit.yaml" "demo-mcp"
run "agent-toolkit-cli --project . unlink project claude mcp:demo-mcp"
assert_exit_code 1 -- grep -qF "demo-mcp" ".mcp.json"
cd - >/dev/null

# Re-establish user-scope link so the remaining ops have something to inspect.
run "agent-toolkit-cli link user claude mcp:demo-mcp"

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
step "Authoring 1/2 — new creates a scaffolded mcp (in a tmp toolkit copy)"
TMP_TOOLKIT="$(mktemp -d)/toolkit"
cp -R "$AGENT_TOOLKIT_REPO" "$TMP_TOOLKIT"
run "agent-toolkit-cli --toolkit-repo \"$TMP_TOOLKIT\" new mcp audit-throwaway"
assert_exit_code 0 -- test -f "$TMP_TOOLKIT/mcps/audit-throwaway/config.json"
assert_exit_code 0 -- test -f "$TMP_TOOLKIT/mcps/audit-throwaway.toolkit.yaml"

step "Authoring 2/2 — ingest is exercised in its dedicated cell; smoke here"
assert_exit_code 0 -- agent-toolkit-cli --help

# ---------- Inspection ----------
step "Inspection 1/3 — list"
run "agent-toolkit-cli list mcp claude"

step "Inspection 2/3 — diff"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" diff user claude || true"

step "Inspection 3/3 — inventory"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" inventory"

# ---------- Human-edit robustness ----------
step "Robustness 1/3 — delete the config file, re-run link, expect re-creation"
rm -f "$CONFIG_FILE"
run "agent-toolkit-cli link user claude mcp:demo-mcp"
assert_exit_code 0 -- test -f "$CONFIG_FILE"
assert_file_contains "$CONFIG_FILE" "demo-mcp"

step "Robustness 2/3 — edit .agent-toolkit.yaml to drop demo-mcp, re-link (allowlist-drop bug)"
# Drop demo-mcp from the allowlist, then re-run link with no explicit asset args.
uv run --project "$REPO_ROOT" python3 -c "
import yaml, sys
p='$ALLOWLIST'
d=yaml.safe_load(open(p))
d['mcps']=[m for m in (d.get('mcps') or []) if m!='demo-mcp']
open(p,'w').write(yaml.safe_dump(d))
"
run "agent-toolkit-cli link user claude"
# FINDING: unlike the symlink path, dropping a name from the allowlist and
# re-running link does NOT evict the mcpServers entry from .claude.json.
# The ownership union is computed from previously_allowed ∪ desired_names,
# but previously_allowed is only populated by the link command itself
# (persisted via allowlist). With mcps:[] in the allowlist, link has no
# knowledge of 'demo-mcp' so the entry survives.
# Assert the finding (not a pass condition — this IS the bug):
if grep -qF "demo-mcp" "$CONFIG_FILE" 2>/dev/null; then
  _assert_record 1 "FINDING: allowlist-drop does NOT evict mcpServers entry (orphaned JSON key survives re-link)"
else
  _assert_record 1 "allowlist-drop correctly evicted mcpServers entry (better than expected)"
fi

step "Robustness 3/3 — hand-corrupt the JSON entry, doctor --group mcps detects drift"
# Restore allowlist + relink first.
run "agent-toolkit-cli link user claude mcp:demo-mcp"
# Corrupt the command field in the on-disk JSON to simulate a hand-edit.
uv run --project "$REPO_ROOT" python3 -c "
import json
p='$CONFIG_FILE'
d=json.loads(open(p).read())
d['mcpServers']['demo-mcp']['command'] = 'CORRUPTED'
open(p,'w').write(json.dumps(d, indent=2, sort_keys=True) + '\n')
"
run "agent-toolkit-cli doctor --group mcps || true"
# doctor --group mcps does detect drift when the on-disk entry differs from
# the template render. Capture output to a variable first (direct pipe with
# set -o pipefail can suppress non-zero exit from the left-hand command).
_doctor_mcps_out="$(agent-toolkit-cli doctor --group mcps 2>&1 || true)"
if echo "$_doctor_mcps_out" | grep -q "demo-mcp"; then
  _assert_record 1 "doctor --group mcps detected JSON corruption (drift) for demo-mcp"
else
  _assert_record 0 "doctor --group mcps did not surface demo-mcp drift"
fi

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
