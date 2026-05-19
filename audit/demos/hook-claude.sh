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

source "$REPO_ROOT/audit/lib/sandbox.sh"
source "$REPO_ROOT/audit/lib/narrate.sh"
source "$REPO_ROOT/audit/lib/assert.sh"
sandbox::init

# Projection shape for (claude, hook):
#   UNSUPPORTED (gap) — no ClaudeHookAdapter exists yet. Fixed via #123:
#   the pair was removed from `_USER_TARGETS` / `_PROJECT_TARGETS` so the
#   CLI no longer silently no-ops. `link user claude hook:<slug>` now exits
#   with the structured "unsupported (harness, kind) pair" error (exit 2)
#   and the allowlist is NOT mutated.
#
#   Re-introduce the row in `_support.py` once `ClaudeHookAdapter` lands.

ALLOWLIST="$HOME/.agent-toolkit.yaml"
HOOKS_SLOT="$CLAUDE_CONFIG_DIR/hooks/demo-hook"
SETTINGS_JSON="$CLAUDE_CONFIG_DIR/settings.json"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user claude hook:demo-hook is rejected (unsupported pair)"
run "agent-toolkit-cli link user claude hook:demo-hook || true"
# Exit code is non-zero (validate_pair → exit 2).
assert_exit_code 2 -- agent-toolkit-cli link user claude hook:demo-hook
# Allowlist is NOT mutated: no `demo-hook` entry under hooks:.
if [[ -f "$ALLOWLIST" ]]; then
  assert_exit_code 1 -- grep -qF "demo-hook" "$ALLOWLIST"
fi
# On-disk materialisation does NOT happen.
assert_exit_code 1 -- test -e "$HOOKS_SLOT"
# settings.json is NOT created.
assert_exit_code 1 -- test -f "$SETTINGS_JSON"
_assert_record 1 "FINDING: (claude, hook) is unsupported (gap) until ClaudeHookAdapter lands — link rejected at validate_pair"
pause 1

step "Lifecycle 2/4 — re-running rejected link is still rejected (idempotency)"
assert_exit_code 2 -- agent-toolkit-cli link user claude hook:demo-hook
if [[ -f "$ALLOWLIST" ]]; then
  assert_exit_code 1 -- grep -qF "demo-hook" "$ALLOWLIST"
fi
pause 1

step "Lifecycle 3/4 — unlink is also rejected (same validate_pair gate)"
assert_exit_code 2 -- agent-toolkit-cli unlink user claude hook:demo-hook
_assert_record 1 "FINDING: unlink mirrors link — unsupported pair refused with exit 2"
pause 1

step "Lifecycle 4/4 — project-scope link is also rejected"
mkdir -p "$HOME/proj" && cd "$HOME/proj"
git init -q
assert_exit_code 2 -- agent-toolkit-cli --project . link project claude hook:demo-hook
if [[ -f ".agent-toolkit.yaml" ]]; then
  assert_exit_code 1 -- grep -qF "demo-hook" ".agent-toolkit.yaml"
fi
assert_exit_code 1 -- test -e ".claude/hooks/demo-hook"
cd - >/dev/null

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
run "agent-toolkit-cli list hook claude || true"

step "Inspection 2/3 — diff"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" diff user claude || true"

step "Inspection 3/3 — inventory"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" inventory"

# ---------- Robustness ----------
step "Robustness 1/2 — settings.json is never written for (claude, hook)"
assert_exit_code 1 -- test -f "$SETTINGS_JSON"
_assert_record 1 "FINDING: settings.json never written (no adapter yet); stale-prune path is unreachable"

step "Robustness 2/2 — once ClaudeHookAdapter lands, re-enable this cell"
# Marker for future audit work: when the adapter is implemented, this cell
# should be rewritten to exercise the materialise + settings.json edit path.
_assert_record 1 "FOLLOWUP: re-author this audit cell when ClaudeHookAdapter exists (#123)"

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
