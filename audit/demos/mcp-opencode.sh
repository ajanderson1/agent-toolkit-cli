#!/usr/bin/env bash
# audit/demos/mcp-opencode.sh — reference cell for mcp × opencode.
#
# Self-hosting: outside tmux, spawns a session and prints the attach
# command; inside tmux, runs the narrated demo and exits with the
# accumulated assertion status.
#
# OpenCode MCP projection uses the "config_file" strategy:
#   - Config path (user):    $HOME/.config/opencode/opencode.json
#   - Config path (project): <project>/.opencode/opencode.json
#   - Edit shape: top-level "mcp" dict, keyed by MCP name.
#   - Unlink: removes the MCP key; leaves file with {} if empty.
#
# Entry shape (stdio):
#   { "type": "local", "command": [...], "enabled": true }

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"

if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-mcp-opencode"
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

# Config paths — resolved after sandbox::init mutates HOME / XDG_CONFIG_HOME.
OC_CONFIG="$XDG_CONFIG_HOME/opencode/opencode.json"
ALLOWLIST="$HOME/.agent-toolkit.yaml"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user opencode mcp:demo-mcp"
run "agent-toolkit-cli link user opencode mcp:demo-mcp"
show "$XDG_CONFIG_HOME/opencode"
assert_exit_code 0 -- test -f "$OC_CONFIG"
assert_file_contains "$OC_CONFIG" "demo-mcp"
assert_file_contains "$ALLOWLIST" "demo-mcp"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
run "agent-toolkit-cli link user opencode mcp:demo-mcp"
assert_file_contains "$OC_CONFIG" "demo-mcp"
pause 1

step "Lifecycle 3/4 — unlink user opencode mcp:demo-mcp"
run "agent-toolkit-cli unlink user opencode mcp:demo-mcp"
show "$OC_CONFIG"
# FINDING: unlink removes the "mcp" key but leaves the file as "{}".
assert_exit_code 1 -- grep -qF "demo-mcp" "$OC_CONFIG"
# File still exists (not deleted) after unlink.
assert_exit_code 0 -- test -f "$OC_CONFIG"
pause 1

step "Lifecycle 4/4 — project-scope link"
mkdir -p "$HOME/proj" && cd "$HOME/proj"
git init -q
# FINDING: project-scope requires .opencode/ dir to exist; the adapter
# creates it automatically via the config_file write path.
run "agent-toolkit-cli --project . link project opencode mcp:demo-mcp"
show ".opencode"
assert_exit_code 0 -- test -f ".opencode/opencode.json"
assert_file_contains ".opencode/opencode.json" "demo-mcp"
assert_file_contains ".agent-toolkit.yaml" "demo-mcp"
run "agent-toolkit-cli --project . unlink project opencode mcp:demo-mcp"
assert_exit_code 1 -- grep -qF "demo-mcp" ".opencode/opencode.json"
cd - >/dev/null

# Re-establish user-scope link so the remaining ops have something to inspect.
run "agent-toolkit-cli link user opencode mcp:demo-mcp"

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
step "Authoring 1/1 — new mcp creates a scaffolded MCP (in a tmp toolkit copy)"
TMP_TOOLKIT="$(mktemp -d)/toolkit"
cp -R "$AGENT_TOOLKIT_REPO" "$TMP_TOOLKIT"
run "agent-toolkit-cli --toolkit-repo \"$TMP_TOOLKIT\" new mcp audit-throwaway"
assert_exit_code 0 -- test -d "$TMP_TOOLKIT/mcps/audit-throwaway"

# ---------- Inspection ----------
step "Inspection 1/3 — list"
run "agent-toolkit-cli list mcp opencode"

step "Inspection 2/3 — diff"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" diff user opencode || true"

step "Inspection 3/3 — inventory"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" inventory"

# ---------- Human-edit robustness ----------
step "Robustness 1/2 — delete config file, re-run link, expect re-creation"
rm -f "$OC_CONFIG"
run "agent-toolkit-cli link user opencode mcp:demo-mcp"
assert_file_contains "$OC_CONFIG" "demo-mcp"

step "Robustness 2/2 — edit .agent-toolkit.yaml to drop demo-mcp, re-link (finding)"
uv run python3 -c "
import yaml, sys
p='$ALLOWLIST'
d=yaml.safe_load(open(p))
d['mcps']=[m for m in (d.get('mcps') or []) if m!='demo-mcp']
open(p,'w').write(yaml.safe_dump(d))
"
run "agent-toolkit-cli link user opencode"
# FINDING: config_file MCPs are NOT pruned by re-link when previously_allowed is
# empty. The ownership set is (previously_allowed ∪ desired_names); with demo-mcp
# removed from the allowlist, desired_names is empty and previously_allowed is also
# empty (no prior reconciliation state), so the adapter leaves demo-mcp in place.
# Explicit `unlink` is required to remove a config-file MCP entry.
# Contrast with skill/symlink adapters where the directory scan tells the engine
# exactly what is present.
if grep -qF "demo-mcp" "$OC_CONFIG"; then
  _assert_record 1 "FINDING: re-link without unlink leaves demo-mcp in config (expected; use unlink to remove)"
else
  _assert_record 1 "demo-mcp removed from config on re-link (better than expected)"
fi

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
