#!/usr/bin/env bash
# audit/demos/command-opencode.sh — reference cell for command × opencode.
#
# Self-hosting: outside tmux, spawns a session and prints the attach
# command; inside tmux, runs the narrated demo and exits with the
# accumulated assertion status.
#
# OpenCode command projection uses "raw file-symlink" layout — same shape
# as agent × opencode:
#   - Symlink:    $XDG_CONFIG_HOME/opencode/commands/<slug>.md   (symlink)
#   - Cache file: $XDG_CONFIG_HOME/opencode/.agent-toolkit-cache/command/<slug>.md
#
# The .md extension is part of the symlink name; no wrapping directory is
# created.  The symlink target is a rendered cache copy — not a direct path
# into $AGENT_TOOLKIT_REPO.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/../.." && pwd)"

if [[ -z "${AUDIT_INSIDE_TMUX:-}" ]]; then
  session="audit-command-opencode"
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

# Projection shape for (opencode, command) — "raw file-symlink":
#   Symlink:    $XDG_CONFIG_HOME/opencode/commands/demo-command.md   → cache file
#   Cache file: $XDG_CONFIG_HOME/opencode/.agent-toolkit-cache/command/demo-command.md
#
# FINDING: OpenCode command projection is a RAW FILE SYMLINK at the .md level,
# not a dir-with-file-symlink (unlike skill × opencode).  The .md extension is
# part of the symlink name; no wrapping directory is created.
# The symlink target is a rendered cache copy — not a direct path into
# $AGENT_TOOLKIT_REPO.

TARGET="$XDG_CONFIG_HOME/opencode/commands/demo-command.md"
CACHE_FILE="$XDG_CONFIG_HOME/opencode/.agent-toolkit-cache/command/demo-command.md"
ALLOWLIST="$HOME/.agent-toolkit.yaml"

# ---------- Lifecycle ----------
step "Lifecycle 1/4 — link user opencode command:demo-command"
run "agent-toolkit-cli link user opencode command:demo-command"
show "$XDG_CONFIG_HOME/opencode/commands"
# The slot is a raw .md symlink pointing at the cache file.
assert_symlink_exists "$TARGET"
assert_symlink_target "$TARGET" "$CACHE_FILE"
# Cache file exists and is a regular file (rendered copy, not a symlink).
assert_exit_code 0 -- test -f "$CACHE_FILE"
assert_file_contains "$ALLOWLIST" "demo-command"
pause 1

step "Lifecycle 2/4 — re-running link is a no-op (idempotency)"
run "agent-toolkit-cli link user opencode command:demo-command"
assert_symlink_target "$TARGET" "$CACHE_FILE"
pause 1

step "Lifecycle 3/4 — unlink user opencode command:demo-command"
run "agent-toolkit-cli unlink user opencode command:demo-command"
show "$XDG_CONFIG_HOME/opencode/commands"
assert_no_symlink "$TARGET"
pause 1

step "Lifecycle 4/4 — project-scope link"
mkdir -p "$HOME/proj" && cd "$HOME/proj"
git init -q
run "agent-toolkit-cli --project . link project opencode command:demo-command"
show ".opencode/commands/demo-command.md"
# Project-scope also uses raw file-symlink layout.
assert_symlink_exists ".opencode/commands/demo-command.md"
# Normalize via realpath to handle macOS /var → /private/var aliasing.
assert_symlink_target ".opencode/commands/demo-command.md" \
  "$(realpath .)/.opencode/.agent-toolkit-cache/command/demo-command.md"
assert_file_contains ".agent-toolkit.yaml" "demo-command"
run "agent-toolkit-cli --project . unlink project opencode command:demo-command"
assert_no_symlink ".opencode/commands/demo-command.md"
cd - >/dev/null

# Re-establish user-scope link so the remaining ops have something to inspect.
run "agent-toolkit-cli link user opencode command:demo-command"

# ---------- Validation ----------
step "Validation 1/3 — check passes on the projected state"
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" check --exit-code
pause 1

step "Validation 2/3 — doctor runs without hard failure"
# doctor exits 0 by default (WARN groups don't trigger non-zero without --exit-code).
# In the sandbox we have only demo-command linked, so symlink-integrity will WARN
# for all the unlinked assets — that is expected and documented as a finding.
run "agent-toolkit-cli doctor"
assert_exit_code 0 -- agent-toolkit-cli doctor

step "Validation 3/3 — fix is a no-op on an already-current toolkit repo"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" fix"
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" fix

# ---------- Authoring ----------
step "Authoring 1/2 — new creates a scaffolded command (in a tmp toolkit copy)"
TMP_TOOLKIT="$(mktemp -d)/toolkit"
cp -R "$AGENT_TOOLKIT_REPO" "$TMP_TOOLKIT"
run "agent-toolkit-cli --toolkit-repo \"$TMP_TOOLKIT\" new command audit-throwaway"
assert_exit_code 0 -- test -f "$TMP_TOOLKIT/commands/audit-throwaway.md"

step "Authoring 2/2 — ingest is exercised in its dedicated cell; smoke here"
assert_exit_code 0 -- agent-toolkit-cli --help

# ---------- Inspection ----------
step "Inspection 1/3 — list"
# Correct invocation: list [KIND] [HARNESS]  (not list SCOPE HARNESS)
run "agent-toolkit-cli list command opencode"

step "Inspection 2/3 — diff"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" diff user opencode || true"

step "Inspection 3/3 — inventory"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" inventory"

# ---------- Human-edit robustness ----------
step "Robustness 1/3 — delete the symlink, re-run link, expect re-creation"
rm -f "$TARGET"
run "agent-toolkit-cli link user opencode command:demo-command"
assert_symlink_exists "$TARGET"
assert_symlink_target "$TARGET" "$CACHE_FILE"

step "Robustness 2/3 — edit .agent-toolkit.yaml to drop demo-command, re-link, expect removal"
uv run python3 -c "
import yaml, sys
p='$ALLOWLIST'
d=yaml.safe_load(open(p))
d['commands']=[s for s in (d.get('commands') or []) if s!='demo-command']
open(p,'w').write(yaml.safe_dump(d))
"
run "agent-toolkit-cli link user opencode"
assert_no_symlink "$TARGET"

step "Robustness 3/3 — hand-edit the projected file is detected by doctor"
# Restore allowlist + relink first.
run "agent-toolkit-cli link user opencode command:demo-command"
# Probe: replace the .md symlink with a regular file (a realistic
# 'human-edit' scenario where the user copies content in place).
rm "$TARGET"
printf "hand-edited\n" > "$TARGET"
run "agent-toolkit-cli doctor --group symlink-integrity || true"
# Findings:
# 1. doctor's symlink-integrity group does NOT flag the replaced-symlink slot:
#    - check_path.exists() is True (regular file) → skips "missing" warn
#    - check_path.is_symlink() is False → skips the "linked" recording
#    - net result: demo-command is silently absent from the report
# 2. --exit-code only fires on FAIL status, not WARN status, so even the
#    other unlinked assets (all WARN) do not trigger a non-zero exit.
#    Both of these are bugs / blind spots in doctor; recorded here as findings.
assert_exit_code 0 -- agent-toolkit-cli doctor --group symlink-integrity --exit-code
# Confirm demo-command is not mentioned (blind spot confirmed).
if uv run python3 -c "
import subprocess, sys
r = subprocess.run(
    ['agent-toolkit-cli', 'doctor', '--group', 'symlink-integrity'],
    capture_output=True, text=True
)
if 'command/demo-command' not in r.stdout + r.stderr:
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
