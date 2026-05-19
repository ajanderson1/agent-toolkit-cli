#!/usr/bin/env bash
# audit/demos/skill-gemini.sh — audit cell for skill × gemini.
#
# FINDING: demo-skill does not declare 'gemini' in its harnesses list
# (declares: claude, codex, opencode, pi).  The CLI correctly rejects the
# link with exit code 1 and the message:
#
#   "skill:demo-skill doesn't support harness 'gemini' (declares: claude,
#    codex, opencode, pi). Use a different harness or pick another asset."
#
# Root cause: no skill in the agent-toolkit repo currently declares 'gemini'
# as a supported harness.  The CLI infrastructure IS in place — 'gemini' is
# listed in ALL_HARNESSES, (_gemini_, skill) maps to ~/.gemini/skills, and
# the projection logic uses raw symlinks for (gemini, skill) — but the asset
# metadata doesn't authorise any skill for the gemini harness.
#
# The T11 empirical-matrix probe recorded supported=true (code_probe) because
# the harness + kind combination has a registered target path, but the probe
# couldn't find a materialised symlink because the link is always rejected
# before projection.  That disagreement is now explained.
#
# The asserts below test the EXPECTED behavior (link succeeds, symlink
# appears).  They will FAIL until a skill declares harness: gemini, surfacing
# this gap in audit/.last-run.tsv and [FAIL] in the generated doc cell.
#
# Self-hosting: outside tmux, spawns a session and prints the attach
# command; inside tmux, runs the narrated demo and exits with the
# accumulated assertion status.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"

if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-skill-gemini"
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

# Projection shape for (gemini, skill) — per _support.py:
#   User target:    ~/.gemini/skills/<slug>   (raw directory symlink)
#   Project target: .gemini/skills/<slug>     (raw directory symlink)
#
# FINDING: link user gemini skill:demo-skill exits 1 because demo-skill
# does not declare 'gemini' in its harnesses list.  The expected path below
# will never be created under current asset metadata.

TARGET="$HOME/.gemini/skills/demo-skill"
EXPECTED_TARGET="$AGENT_TOOLKIT_REPO/skills/demo-skill"
ALLOWLIST="$HOME/.agent-toolkit.yaml"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user gemini skill:demo-skill"
# Expected: exits 0, creates symlink at ~/.gemini/skills/demo-skill.
# Observed: exits 1 — demo-skill doesn't declare harness 'gemini'.
# The assert_exit_code below records the FINDING as a visible FAIL.
run "agent-toolkit-cli link user gemini skill:demo-skill || true"
assert_exit_code 0 -- agent-toolkit-cli link user gemini skill:demo-skill
# Downstream symlink asserts will also fail, amplifying the finding signal.
assert_symlink_exists "$TARGET"
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"
assert_file_contains  "$ALLOWLIST" "demo-skill"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
# Also expected to fail for the same reason.
assert_exit_code 0 -- agent-toolkit-cli link user gemini skill:demo-skill
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"
pause 1

step "Lifecycle 3/4 — unlink user gemini skill:demo-skill"
run "agent-toolkit-cli unlink user gemini skill:demo-skill || true"
assert_no_symlink "$TARGET"
pause 1

step "Lifecycle 4/4 — project-scope link"
mkdir -p "$HOME/proj" && cd "$HOME/proj"
git init -q
run "agent-toolkit-cli --project . link project gemini skill:demo-skill || true"
assert_exit_code 0 -- agent-toolkit-cli --project . link project gemini skill:demo-skill
# Also fails for the same reason.
assert_exit_code 0 -- test -e ".gemini/skills/demo-skill"
cd - >/dev/null

# ---------- Validation ----------
step "Validation 1/2 — doctor runs without hard failure"
# doctor exits 0 by default; the sandbox has nothing linked so symlink-integrity
# group warns for all unlinked assets — expected and documented.
run "agent-toolkit-cli doctor"
assert_exit_code 0 -- agent-toolkit-cli doctor

step "Validation 2/2 — list skill gemini"
# list should exit 0 even when nothing is linked.
run "agent-toolkit-cli list skill gemini || true"
assert_exit_code 0 -- agent-toolkit-cli list skill gemini

# ---------- Inspection ----------
step "Inspection — diff user gemini"
run "agent-toolkit-cli diff user gemini || true"

# ---------- Finding summary ----------
step "Finding — no skill declares harness: gemini"
# Confirm the rejection is caused by missing frontmatter, not a CLI crash.
# The CLI emits a clear message; we record the finding as a named assertion.
gemini_out=""
gemini_rc=0
gemini_out=$(agent-toolkit-cli link user gemini skill:demo-skill 2>&1) || gemini_rc=$?
if echo "$gemini_out" | grep -q "doesn't support harness 'gemini'"; then
  _assert_record 1 "FINDING CONFIRMED: link rejects skill:demo-skill with 'doesn't support harness gemini' (rc=$gemini_rc)"
else
  _assert_record 0 "FINDING: unexpected link output — $gemini_out"
fi

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
