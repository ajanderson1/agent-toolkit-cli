#!/usr/bin/env bash
# audit/demos/hook-codex.sh — audit cell for hook × codex.
#
# FINDING: demo-hook does not declare 'codex' in its harnesses list
# (declares: claude).  The CLI correctly rejects the link with exit
# code 1 and the message:
#
#   "hook:demo-hook doesn't support harness 'codex' (declares: claude).
#    Use a different harness or pick another asset."
#
# Root cause: demo-hook declares spec.harnesses: [claude] — codex is absent.
# The CLI infrastructure IS in place — ("codex", "hook") is in _USER_TARGETS
# and maps to ~/.codex/agent-toolkit-hooks — but the asset metadata does not
# authorise demo-hook for the codex harness.
#
# The asserts below test the EXPECTED behavior (link succeeds, folder appears).
# They will FAIL until demo-hook declares harness: codex, surfacing this gap
# in audit/.last-run.tsv and [FAIL] in the generated doc cell.
#
# Self-hosting: outside tmux, spawns a session and prints the attach
# command; inside tmux, runs the narrated demo and exits with the
# accumulated assertion status.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"

if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-hook-codex"
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

# Projection shape for (codex, hook) — per _support.py:
#   User target:    ~/.codex/agent-toolkit-hooks/<slug>   (config_file+folder)
#   Project target: .codex/agent-toolkit-hooks/<slug>
#
# FINDING: link user codex hook:demo-hook exits 1 because demo-hook
# does not declare 'codex' in its harnesses list.  The expected path
# below will never be created under current asset metadata.

TARGET="$HOME/.codex/agent-toolkit-hooks/demo-hook"
ALLOWLIST="$HOME/.agent-toolkit.yaml"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user codex hook:demo-hook"
# Expected: exits 0, creates hook folder at ~/.codex/agent-toolkit-hooks/demo-hook.
# Observed: exits 1 — demo-hook doesn't declare harness 'codex'.
# The assert_exit_code below records the FINDING as a visible FAIL.
run "agent-toolkit-cli link user codex hook:demo-hook || true"
assert_exit_code 0 -- agent-toolkit-cli link user codex hook:demo-hook
# Downstream path asserts will also fail, amplifying the finding signal.
assert_no_symlink "$TARGET"
assert_file_contains "$ALLOWLIST" "demo-hook"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
# Also expected to fail for the same reason.
assert_exit_code 0 -- agent-toolkit-cli link user codex hook:demo-hook
assert_no_symlink "$TARGET"
pause 1

step "Lifecycle 3/4 — unlink user codex hook:demo-hook"
run "agent-toolkit-cli unlink user codex hook:demo-hook || true"
assert_no_symlink "$TARGET"
pause 1

step "Lifecycle 4/4 — project-scope link"
mkdir -p "$HOME/proj" && cd "$HOME/proj"
git init -q
run "agent-toolkit-cli --project . link project codex hook:demo-hook || true"
assert_exit_code 0 -- agent-toolkit-cli --project . link project codex hook:demo-hook
# Also fails for the same reason.
assert_exit_code 0 -- test -e ".codex/agent-toolkit-hooks/demo-hook"
cd - >/dev/null

# ---------- Validation ----------
step "Validation 1/2 — doctor runs without hard failure"
run "agent-toolkit-cli doctor"
assert_exit_code 0 -- agent-toolkit-cli doctor

step "Validation 2/2 — list hook codex"
run "agent-toolkit-cli list hook codex || true"
assert_exit_code 0 -- agent-toolkit-cli list hook codex

# ---------- Inspection ----------
step "Inspection — diff user codex"
run "agent-toolkit-cli diff user codex || true"

# ---------- Finding summary ----------
step "Finding — demo-hook does not declare harness: codex"
# Confirm the rejection is caused by missing frontmatter, not a CLI crash.
# The CLI emits a clear message; we record the finding as a named assertion.
codex_out=""
codex_rc=0
codex_out=$(agent-toolkit-cli link user codex hook:demo-hook 2>&1) || codex_rc=$?
if echo "$codex_out" | grep -q "doesn't support harness 'codex'"; then
  _assert_record 1 "FINDING CONFIRMED: link rejects hook:demo-hook with 'doesn't support harness codex' (rc=$codex_rc)"
else
  _assert_record 0 "FINDING: unexpected link output — $codex_out"
fi

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
