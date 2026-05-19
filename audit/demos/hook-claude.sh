#!/usr/bin/env bash
# audit/demos/hook-claude.sh — audit cell for hook × claude.
#
# Self-hosting: outside tmux, spawns a session and prints the attach
# command; inside tmux, runs the narrated demo and exits with the
# accumulated assertion status.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"

if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-hook-claude"
  tmux kill-session -t "$session" 2>/dev/null || true
  tmux new-session -d -s "$session" "AUDIT_INSIDE_TMUX=1 bash $SCRIPT_PATH"
  printf 'tmux attach -t %s\n' "$session"
  exit 0
fi

# --- inside tmux ---

# Override AGENT_TOOLKIT_REPO to point at the companion PR worktree where
# demo-hook lives. PR #17 is open at https://github.com/ajanderson1/agent-toolkit/pull/17.
# TODO: drop this override once PR #17 merges to main.
export AGENT_TOOLKIT_REPO="/Users/ajanderson/GitHub/agent-toolkit/.worktrees/audit-demos-1779206947"

source "$REPO_ROOT/audit/lib/sandbox.sh"
source "$REPO_ROOT/audit/lib/narrate.sh"
source "$REPO_ROOT/audit/lib/assert.sh"
sandbox::init

# Projection shape for (claude, hook):
#   UNIMPLEMENTED — no ClaudeHookAdapter exists yet.
#
#   `get_adapter("claude", kind="hook")` returns UnimplementedAdapter.
#   The link command therefore:
#     1. Adds the slug to the allowlist (.agent-toolkit.yaml under [hooks]).
#     2. Skips the config_file+folder materialisation entirely, printing:
#        "no MCP adapter for harness claude yet — skipping"
#     3. Does NOT create any file under $HOME/.claude/hooks/<slug>/.
#     4. Does NOT mutate $HOME/.claude/settings.json.
#
#   This is the primary finding of this cell. All lifecycle assertions below
#   verify the allowlist side (what DOES happen) and confirm the on-disk
#   materialisation gap (what DOESN'T happen).

ALLOWLIST="$HOME/.agent-toolkit.yaml"
HOOKS_SLOT="$CLAUDE_CONFIG_DIR/hooks/demo-hook"
SETTINGS_JSON="$CLAUDE_CONFIG_DIR/settings.json"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user claude hook:demo-hook"
run "agent-toolkit-cli link user claude hook:demo-hook"
# Allowlist IS written — the slug lands in [hooks].
assert_file_contains "$ALLOWLIST" "demo-hook"
# On-disk materialisation does NOT happen — no file under ~/.claude/hooks/demo-hook/.
assert_exit_code 1 -- test -e "$HOOKS_SLOT"
# settings.json is NOT created.
assert_exit_code 1 -- test -f "$SETTINGS_JSON"
# FINDING: (claude, hook) is allowlist-only; the hook script is never materialised
# and settings.json is never edited because ClaudeHookAdapter does not exist.
_assert_record 1 "FINDING: claude hook materialisation unimplemented — allowlist written, no files on disk"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
run "agent-toolkit-cli link user claude hook:demo-hook"
# Still in allowlist.
assert_file_contains "$ALLOWLIST" "demo-hook"
# Still no on-disk slot.
assert_exit_code 1 -- test -e "$HOOKS_SLOT"
pause 1

step "Lifecycle 3/4 — unlink user claude hook:demo-hook"
run "agent-toolkit-cli unlink user claude hook:demo-hook"
# Unlink removes slug from allowlist.
assert_exit_code 1 -- grep -qF "demo-hook" "$ALLOWLIST"
# Nothing to remove on disk — no slot existed.
# FINDING: unlink is a clean no-op on-disk (nothing to remove; allowlist is authoritative).
_assert_record 1 "FINDING: unlink is clean no-op on-disk (no slot was ever materialised)"
pause 1

step "Lifecycle 4/4 — project-scope link"
mkdir -p "$HOME/proj" && cd "$HOME/proj"
git init -q
run "agent-toolkit-cli --project . link project claude hook:demo-hook"
# Project-scope allowlist written.
assert_file_contains ".agent-toolkit.yaml" "demo-hook"
# Project-scope on-disk slot also absent (same unimplemented adapter).
assert_exit_code 1 -- test -e ".claude/hooks/demo-hook"
run "agent-toolkit-cli --project . unlink project claude hook:demo-hook"
assert_exit_code 1 -- grep -qF "demo-hook" ".agent-toolkit.yaml"
cd - >/dev/null

# Re-establish user-scope link so the remaining ops have something to inspect.
run "agent-toolkit-cli link user claude hook:demo-hook"

# ---------- Validation ----------
step "Validation 1/3 — check passes on the projected state"
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" check --exit-code
pause 1

step "Validation 2/3 — doctor runs without hard failure"
# doctor exits 0 by default (WARN groups don't trigger non-zero without --exit-code).
run "agent-toolkit-cli doctor"
assert_exit_code 0 -- agent-toolkit-cli doctor

step "Validation 3/3 — fix is a no-op on an already-current toolkit repo"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" fix"
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" fix

# ---------- Authoring ----------
step "Authoring 1/2 — new creates a scaffolded hook (in a tmp toolkit copy)"
TMP_TOOLKIT="$(mktemp -d)/toolkit"
cp -R "$AGENT_TOOLKIT_REPO" "$TMP_TOOLKIT"
run "agent-toolkit-cli --toolkit-repo \"$TMP_TOOLKIT\" new hook audit-hk-cl-throwaway"
# The new hook command creates a flat .meta.yaml (not a directory).
assert_exit_code 0 -- test -f "$TMP_TOOLKIT/hooks/audit-hk-cl-throwaway.meta.yaml"

step "Authoring 2/2 — ingest is exercised in its dedicated cell; smoke here"
assert_exit_code 0 -- agent-toolkit-cli --help

# ---------- Inspection ----------
step "Inspection 1/3 — list"
run "agent-toolkit-cli list hook claude"

step "Inspection 2/3 — diff"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" diff user claude || true"

step "Inspection 3/3 — inventory"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" inventory"

# ---------- Human-edit robustness ----------
step "Robustness 1/3 — drop demo-hook from allowlist, re-run link, confirm absent"
# Use uv run python3 so PyYAML is available.
uv run python3 -c "
import yaml, sys
p='$ALLOWLIST'
d=yaml.safe_load(open(p))
d['hooks']=[s for s in (d.get('hooks') or []) if s!='demo-hook']
open(p,'w').write(yaml.safe_dump(d))
"
run "agent-toolkit-cli link user claude"
assert_exit_code 1 -- grep -qF "demo-hook" "$ALLOWLIST"

step "Robustness 2/3 — doctor blind-spot: no on-disk slot to inspect"
# Re-link to have the slug in the allowlist.
run "agent-toolkit-cli link user claude hook:demo-hook"
# With no ClaudeHookAdapter, doctor has no materialised artefact to check.
# symlink-integrity only walks the slot dir; if the slot dir doesn't exist
# (which it won't for unimplemented adapters), all hooks are silently absent
# from the report.
run "agent-toolkit-cli doctor --group symlink-integrity || true"
assert_exit_code 0 -- agent-toolkit-cli doctor --group symlink-integrity --exit-code
if uv run python3 -c "
import subprocess, sys
r = subprocess.run(
    ['agent-toolkit-cli', 'doctor', '--group', 'symlink-integrity'],
    capture_output=True, text=True
)
if 'demo-hook' not in r.stdout + r.stderr:
    sys.exit(0)  # not mentioned = blind spot confirmed
sys.exit(1)  # mentioned = doctor caught it
"; then
  _assert_record 1 "FINDING: doctor blind to hook:demo-hook (no slot exists; adapter unimplemented)"
else
  _assert_record 1 "doctor surfaced hook:demo-hook (better than expected)"
fi

step "Robustness 3/3 — settings.json never written; no stale-prune scenario"
# Since settings.json is never written, there is no stale-prune scenario.
# This is a structural gap: if a user manually adds a hook to settings.json
# and then unlinks the toolkit, the stale entry is invisible to the CLI.
assert_exit_code 1 -- test -f "$SETTINGS_JSON"
_assert_record 1 "FINDING: settings.json never written; stale-prune path is unreachable"

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
