#!/usr/bin/env bash
# audit/demos/mcp-codex.sh — audit cell for mcp × codex.
#
# Config-file strategy: the CLI writes a TOML stanza into:
#   user scope:    $CODEX_HOME/config.toml  (= ~/.codex/config.toml)
#   project scope: <project>/.codex/config.toml  (only when .codex/ dir exists)
#
# Stanza shape (stdio transport):
#   [mcp_servers.demo-mcp]
#   command = "npx"
#   args = ["-y", "@modelcontextprotocol/server-everything"]
#
# Unlink: removes the [mcp_servers.demo-mcp] table; file becomes empty (0B)
# when demo-mcp was the only entry (confirmed in recon).
#
# Self-hosting: outside tmux, spawns a session and prints the attach
# command; inside tmux, runs the narrated demo and exits with the
# accumulated assertion status.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"

if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-mcp-codex"
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

# Projection shape for (codex, mcp):
#   Config-file strategy — no symlink.
#   The CLI writes a [mcp_servers.demo-mcp] TOML stanza into:
#     $CODEX_HOME/config.toml  (user scope)
#     <project>/.codex/config.toml  (project scope, requires .codex/ dir)
#   Stanza for stdio transport:
#     command = "npx"
#     args    = ["-y", "@modelcontextprotocol/server-everything"]
#   Unlink removes the stanza (file truncated to empty when it was the only entry).

CONFIG_FILE="$CODEX_HOME/config.toml"
ALLOWLIST="$HOME/.agent-toolkit.yaml"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user codex mcp:demo-mcp"
run "agent-toolkit-cli link user codex mcp:demo-mcp"
show "$CONFIG_FILE"
assert_file_contains "$CONFIG_FILE" "demo-mcp"
assert_file_contains "$ALLOWLIST"   "demo-mcp"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
run "agent-toolkit-cli link user codex mcp:demo-mcp"
assert_file_contains "$CONFIG_FILE" "demo-mcp"
pause 1

step "Lifecycle 3/4 — unlink user codex mcp:demo-mcp"
run "agent-toolkit-cli unlink user codex mcp:demo-mcp"
show "$CONFIG_FILE"
# Unlink removes the stanza; grep exits 1 = entry is gone.
assert_exit_code 1 -- grep -qF "demo-mcp" "$CONFIG_FILE"
pause 1

step "Lifecycle 4/4 — project-scope link"
mkdir -p "$HOME/proj/.codex" && cd "$HOME/proj"
git init -q
run "agent-toolkit-cli --project . link project codex mcp:demo-mcp"
show ".codex/config.toml"
# Project config must contain the stanza.
assert_file_contains ".codex/config.toml" "demo-mcp"
assert_file_contains ".agent-toolkit.yaml" "demo-mcp"
run "agent-toolkit-cli --project . unlink project codex mcp:demo-mcp"
assert_exit_code 1 -- grep -qF "demo-mcp" ".codex/config.toml"
cd - >/dev/null

# Re-establish user-scope link so the remaining ops have something to inspect.
run "agent-toolkit-cli link user codex mcp:demo-mcp"

# ---------- Validation ----------
step "Validation 1/3 — check passes on the projected state"
# check validates asset frontmatter + AGENTS.md regions; exits 0 when all is OK.
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" check --exit-code
pause 1

step "Validation 2/3 — doctor runs without hard failure"
# doctor exits 0 by default (WARN groups don't trigger non-zero without --exit-code).
run "agent-toolkit-cli doctor"
assert_exit_code 0 -- agent-toolkit-cli doctor

step "Validation 3/3 — fix is a no-op on an already-current toolkit repo"
# fix regenerates AGENTS.md auto-regions; exits 0 whether or not it wrote changes.
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" fix"
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" fix

# ---------- Authoring ----------
step "Authoring — new mcp audit-throwaway"
TMP_TOOLKIT="$(mktemp -d)/toolkit"
cp -R "$AGENT_TOOLKIT_REPO" "$TMP_TOOLKIT"
run "agent-toolkit-cli --toolkit-repo \"$TMP_TOOLKIT\" new mcp audit-throwaway"
assert_exit_code 0 -- test -d "$TMP_TOOLKIT/mcps/audit-throwaway"

# ---------- Inspection ----------
step "Inspection 1/3 — list"
run "agent-toolkit-cli list mcp codex"

step "Inspection 2/3 — diff"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" diff user codex || true"

step "Inspection 3/3 — inventory"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" inventory"

# ---------- Human-edit robustness ----------
step "Robustness 1/3 — delete config.toml, re-run link, expect re-creation"
rm -f "$CONFIG_FILE"
run "agent-toolkit-cli link user codex mcp:demo-mcp"
assert_file_contains "$CONFIG_FILE" "demo-mcp"

step "Robustness 2/3 — edit .agent-toolkit.yaml to drop demo-mcp, re-link, observe"
# For config-file strategy, ownership is tracked via previously_allowed (the
# pre-mutation allowlist).  When the allowlist is mutated by hand before
# re-running link, the CLI no longer knows it ever owned the stanza; it
# cannot distinguish it from a hand-rolled entry.  Consequently the stanza
# is preserved rather than removed.
#
# FINDING: dropping an MCP from the allowlist by hand then running
#   agent-toolkit-cli link user codex
# leaves the [mcp_servers.demo-mcp] stanza in config.toml (orphaned).
# The symlink-based strategy (claude, codex skills) does not have this issue
# because presence/absence of the symlink IS the state.
uv run python3 -c "
import yaml, sys
p='$ALLOWLIST'
d=yaml.safe_load(open(p))
d['mcps']=[m for m in (d.get('mcps') or []) if m!='demo-mcp']
open(p,'w').write(yaml.safe_dump(d))
"
run "agent-toolkit-cli link user codex"
# Record the finding: stanza is orphaned (grep exits 0 = still present).
link_rc=0
grep -qF "demo-mcp" "$CONFIG_FILE" || link_rc=$?
if [ "$link_rc" -eq 0 ]; then
  _assert_record 1 "FINDING: hand-edit allowlist drop orphans config-file stanza — stanza still present after re-link"
else
  _assert_record 1 "stanza was removed (better than expected)"
fi

step "Robustness 3/3 — hand-edit TOML stanza to break it, run doctor, observe"
# Restore the link first.
run "agent-toolkit-cli link user codex mcp:demo-mcp"
# Break the stanza: replace a well-formed key with invalid TOML.
uv run python3 -c "
p = '$CONFIG_FILE'
txt = open(p).read()
txt = txt.replace('command = \"npx\"', 'command = INVALID-TOML')
open(p, 'w').write(txt)
"
run "agent-toolkit-cli doctor || true"
# Finding: doctor does not parse config-file contents — it only checks the
# allowlist vs. list_installed(). A broken TOML may prevent list_installed()
# from reading the file at all, surfacing 0 installed entries rather than a
# FAIL status.  Record whichever outcome is observed.
doctor_out=""
doctor_rc=0
doctor_out=$(agent-toolkit-cli doctor 2>&1) || doctor_rc=$?
if echo "$doctor_out" | grep -qi "demo-mcp"; then
  _assert_record 1 "doctor mentioned demo-mcp after TOML corruption (rc=$doctor_rc)"
else
  _assert_record 1 "FINDING: doctor silent on broken TOML — list_installed fails to parse, entry invisible (rc=$doctor_rc)"
fi

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
