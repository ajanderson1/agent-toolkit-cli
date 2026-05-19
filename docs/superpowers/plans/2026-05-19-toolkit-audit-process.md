# Toolkit Audit Process Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a development-time toolkit audit — per-cell narrated tmux demos with hard assertions, a triangulated support matrix, and a hand-curated findings doc — for every supported `(kind × harness)` combination of the agent-toolkit CLI.

**Architecture:** Bash helpers (`audit/lib/`) plus one Python introspection helper drive self-hosting tmux demo scripts (`audit/demos/`) that run inside ephemeral sandbox `HOME`s. A scaffolder (`audit/build-doc.sh`) merges discovered cells into a hand-edited findings doc (`docs/audit/2026-05-19-toolkit-audit.md`) via marker-bounded regions. The toolkit repo gets two new permanent demo assets (`demo-hook`, `demo-pi-extension`) in a companion PR.

**Tech Stack:** bash 3.2+ (macOS default), tmux, jq, Python 3.12 (for the one code probe), pytest (only to verify existing CLI didn't regress; audit helpers are shell-tested).

**Spec:** `docs/superpowers/specs/2026-05-19-toolkit-audit-process-design.md`.

**Worktree convention:** Per the global CLAUDE.md, work in `.worktrees/audit-process-<timestamp>/` for this repo. The companion-PR work in the toolkit repo uses its own worktree at `~/GitHub/agent-toolkit/.worktrees/audit-demos-<timestamp>/`.

---

## File Structure

### This repo (`agent-toolkit-cli`)

| Path | Responsibility |
|---|---|
| `audit/lib/sandbox.sh` | Tmpdir + per-harness env vars + EXIT trap |
| `audit/lib/narrate.sh` | `step`, `run`, `show`, `pause` for paced TTY narration |
| `audit/lib/assert.sh` | Accumulating assertions + `assertions::finish` exit code |
| `audit/lib/code_probe.py` | Introspect `harness_adapters` + `link` to enumerate `(harness, kind) → target_dir` |
| `audit/discover-matrix.sh` | Emit TSV `kind \t harness \t source \t supported` from three probes |
| `audit/build-doc.sh` | Idempotent-merge scaffolder for the findings doc |
| `audit/run-all.sh` | Run every demo, write `audit/.last-run.tsv` |
| `audit/demos/skill-claude.sh` | Reference cell |
| `audit/demos/<kind>-<harness>.sh` | One per supported cell (fan-out) |
| `tests/audit/test_sandbox.sh` | Shell tests for `sandbox.sh` |
| `tests/audit/test_narrate.sh` | Shell tests for `narrate.sh` |
| `tests/audit/test_assert.sh` | Shell tests for `assert.sh` |
| `tests/audit/test_code_probe.sh` | Shell test wrapping `code_probe.py` |
| `tests/audit/test_discover_matrix.sh` | Snapshot test for `discover-matrix.sh` |
| `tests/audit/test_build_doc.sh` | Idempotency + marker-preservation tests |
| `tests/audit/lib.sh` | Test runner sourced by each shell test (tiny `assert`/`run` helpers) |
| `docs/audit/2026-05-19-toolkit-audit.md` | The living findings document |

### Companion PR in `~/GitHub/agent-toolkit/`

| Path | Responsibility |
|---|---|
| `hooks/demo-hook.meta.yaml` | Metadata sidecar for `demo-hook` |
| `hooks/demo-hook.sh` | Trivial PreToolUse hook body — echoes a marker line |
| `extensions/demo-pi-extension/extension.meta.yaml` | Metadata for `demo-pi-extension` |
| `extensions/demo-pi-extension/index.ts` | Trivial Pi extension body |
| `extensions/demo-pi-extension/package.json` | Minimal manifest mirroring `status-bar/` |

---

## Task 0: Create worktree

**Files:** none yet — this task creates the working directory.

- [ ] **Step 1: Create the worktree**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli
git worktree add ".worktrees/audit-process-$(date +%s)" -b audit-process
cd .worktrees/audit-process-*
```

- [ ] **Step 2: Verify clean state**

Run: `git status`
Expected: `On branch audit-process … nothing to commit, working tree clean` (the `.agent-toolkit.yaml` and `CLAUDE.md` untracked files belong to the main checkout, not this worktree).

---

## Task 1: Test-runner harness for shell tests

We need a tiny pure-bash test runner before writing any helpers. Each shell test file sources `tests/audit/lib.sh` and uses `t::assert "msg" '[ condition ]'` and `t::run name body`.

**Files:**
- Create: `tests/audit/lib.sh`
- Create: `tests/audit/test_lib.sh` (self-test for the runner)

- [ ] **Step 1: Write the failing self-test for the runner**

Create `tests/audit/test_lib.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

t::run "passes a true assertion" '
  t::assert "1 equals 1" "[ 1 = 1 ]"
'

t::run "fails a false assertion" '
  if t::assert "1 equals 2" "[ 1 = 2 ]" 2>/dev/null; then
    echo "expected failure but assertion passed" >&2
    return 1
  fi
'

t::summary
```

- [ ] **Step 2: Run it to confirm failure (lib.sh does not exist)**

Run: `bash tests/audit/test_lib.sh`
Expected: error like `tests/audit/lib.sh: No such file or directory`.

- [ ] **Step 3: Write `tests/audit/lib.sh`**

```bash
# tests/audit/lib.sh — minimal pure-bash test runner.
# Sourced by every audit shell test. Tracks pass/fail counts; `t::summary`
# exits non-zero if any test failed.

T_PASS=0
T_FAIL=0
T_CURRENT=""

t::run() {
  local name="$1" body="$2"
  T_CURRENT="$name"
  if ( eval "$body" ); then
    printf '  ok  %s\n' "$name"
    T_PASS=$((T_PASS + 1))
  else
    printf '  FAIL %s\n' "$name" >&2
    T_FAIL=$((T_FAIL + 1))
  fi
  T_CURRENT=""
}

t::assert() {
  local msg="$1" cond="$2"
  if eval "$cond"; then
    return 0
  fi
  printf '    assert failed: %s (cond: %s)\n' "$msg" "$cond" >&2
  return 1
}

t::summary() {
  printf '\n%d passed, %d failed\n' "$T_PASS" "$T_FAIL"
  [ "$T_FAIL" -eq 0 ]
}
```

- [ ] **Step 4: Run the self-test and confirm pass**

Run: `bash tests/audit/test_lib.sh`
Expected: ends with `2 passed, 0 failed` and exit code 0.

- [ ] **Step 5: Commit**

```bash
git add tests/audit/lib.sh tests/audit/test_lib.sh
git commit -m "test(audit): minimal bash test runner for audit helpers"
```

---

## Task 2: `sandbox.sh` helper

**Files:**
- Create: `audit/lib/sandbox.sh`
- Create: `tests/audit/test_sandbox.sh`

- [ ] **Step 1: Write the failing test**

Create `tests/audit/test_sandbox.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=/dev/null
source "$REPO_ROOT/audit/lib/sandbox.sh"

t::run "init sets HOME under a tmpdir and exports harness vars" '
  sandbox::init
  t::assert "HOME is set"            "[ -n \"\$HOME\" ]"
  t::assert "HOME is a directory"    "[ -d \"\$HOME\" ]"
  t::assert "HOME prefix is tmpdir"  "[[ \"\$HOME\" == */agent-toolkit-audit.* ]]"
  t::assert "CLAUDE_CONFIG_DIR set"  "[ -n \"\${CLAUDE_CONFIG_DIR:-}\" ]"
  t::assert "CODEX_HOME set"         "[ -n \"\${CODEX_HOME:-}\" ]"
  t::assert "XDG_CONFIG_HOME set"    "[ -n \"\${XDG_CONFIG_HOME:-}\" ]"
  t::assert "AGENT_TOOLKIT_REPO set" "[ -n \"\${AGENT_TOOLKIT_REPO:-}\" ]"
  t::assert "toolkit repo exists"    "[ -d \"\$AGENT_TOOLKIT_REPO\" ]"
'

t::run "cleanup removes the tmpdir" '
  sandbox::init
  local h="$HOME"
  sandbox::cleanup
  t::assert "tmpdir removed" "[ ! -d \"$h\" ]"
'

t::summary
```

- [ ] **Step 2: Run to confirm failure**

Run: `bash tests/audit/test_sandbox.sh`
Expected: error sourcing `audit/lib/sandbox.sh` (file not found).

- [ ] **Step 3: Write `audit/lib/sandbox.sh`**

```bash
# audit/lib/sandbox.sh — ephemeral sandbox HOME for audit demos.
#
# Usage:
#   source audit/lib/sandbox.sh
#   sandbox::init           # mutates env, registers EXIT trap
#   sandbox::cleanup        # callable manually; trap calls it on exit

SANDBOX_DEFAULT_TOOLKIT_REPO="${AGENT_TOOLKIT_REPO:-$HOME/GitHub/agent-toolkit}"

sandbox::init() {
  local tmp
  tmp="$(mktemp -d -t agent-toolkit-audit.XXXXXX)"
  export SANDBOX_TMPDIR="$tmp"
  export HOME="$tmp"
  export XDG_CONFIG_HOME="$tmp/.config"
  export CLAUDE_CONFIG_DIR="$tmp/.claude"
  export CODEX_HOME="$tmp/.codex"
  # OpenCode/Gemini/Pi: HOME redirection is the universal fallback.
  # If empirical testing in later tasks shows a harness needs a dedicated
  # var, add it here.
  export AGENT_TOOLKIT_REPO="$SANDBOX_DEFAULT_TOOLKIT_REPO"
  mkdir -p "$XDG_CONFIG_HOME" "$CLAUDE_CONFIG_DIR" "$CODEX_HOME"
  trap 'sandbox::cleanup' EXIT
}

sandbox::cleanup() {
  if [ -n "${SANDBOX_TMPDIR:-}" ] && [ -d "$SANDBOX_TMPDIR" ]; then
    rm -rf "$SANDBOX_TMPDIR"
  fi
  unset SANDBOX_TMPDIR
}
```

- [ ] **Step 4: Run test, confirm pass**

Run: `bash tests/audit/test_sandbox.sh`
Expected: `2 passed, 0 failed`.

- [ ] **Step 5: Commit**

```bash
git add audit/lib/sandbox.sh tests/audit/test_sandbox.sh
git commit -m "feat(audit): sandbox::init for ephemeral HOME with per-harness vars"
```

---

## Task 3: `narrate.sh` helper

**Files:**
- Create: `audit/lib/narrate.sh`
- Create: `tests/audit/test_narrate.sh`

- [ ] **Step 1: Write the failing test**

Create `tests/audit/test_narrate.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib.sh"
source "$REPO_ROOT/audit/lib/narrate.sh"

t::run "step prints the heading to stdout" '
  local out
  out="$(step "hello" 2>&1)"
  t::assert "heading appeared" "[[ \"$out\" == *hello* ]]"
'

t::run "run echoes then executes the command" '
  local out
  out="$(run "echo from-run" 2>&1)"
  t::assert "command echoed" "[[ \"$out\" == *echo\\ from-run* ]]"
  t::assert "command output appeared" "[[ \"$out\" == *from-run* ]]"
'

t::run "show on a missing path prints a clear marker" '
  local out
  out="$(show "/no/such/path" 2>&1)"
  t::assert "missing marker" "[[ \"$out\" == *MISSING* ]]"
'

t::run "pause respects PAUSE_SCALE=0" '
  local start end
  start=$(date +%s)
  PAUSE_SCALE=0 pause 5
  end=$(date +%s)
  t::assert "pause skipped" "[ $((end - start)) -lt 2 ]"
'

t::summary
```

- [ ] **Step 2: Run to confirm failure**

Run: `bash tests/audit/test_narrate.sh`
Expected: source error (file not found).

- [ ] **Step 3: Write `audit/lib/narrate.sh`**

```bash
# audit/lib/narrate.sh — paced narration helpers for audit demos.
#
# step <heading>             # bold heading + newline
# run  <cmd>                 # echo command, then eval it
# show <path>                # ls -la + readlink (symlink) or head -20 (file)
# pause <seconds>            # sleep, scaled by $PAUSE_SCALE (default 1)

_narrate_bold() {
  if [ -t 1 ]; then
    printf '\033[1m%s\033[0m\n' "$1"
  else
    printf '%s\n' "$1"
  fi
}

step() {
  printf '\n'
  _narrate_bold "# $*"
}

run() {
  _narrate_bold "$ $*"
  eval "$@"
}

show() {
  local path="$1"
  if [ ! -e "$path" ] && [ ! -L "$path" ]; then
    printf '  MISSING: %s\n' "$path"
    return 0
  fi
  ls -la "$path"
  if [ -L "$path" ]; then
    printf '  -> %s\n' "$(readlink "$path")"
  elif [ -f "$path" ]; then
    head -20 "$path"
  fi
}

pause() {
  local seconds="$1"
  local scale="${PAUSE_SCALE:-1}"
  # POSIX sh has no float arithmetic; rely on awk.
  local actual
  actual="$(awk -v s="$seconds" -v k="$scale" 'BEGIN { print s * k }')"
  # Skip the sleep entirely if scale is 0.
  if [ "$scale" = "0" ]; then
    return 0
  fi
  sleep "$actual"
}
```

- [ ] **Step 4: Run test, confirm pass**

Run: `bash tests/audit/test_narrate.sh`
Expected: `4 passed, 0 failed`.

- [ ] **Step 5: Commit**

```bash
git add audit/lib/narrate.sh tests/audit/test_narrate.sh
git commit -m "feat(audit): narrate.sh step/run/show/pause helpers"
```

---

## Task 4: `assert.sh` helper

**Files:**
- Create: `audit/lib/assert.sh`
- Create: `tests/audit/test_assert.sh`

- [ ] **Step 1: Write the failing test**

Create `tests/audit/test_assert.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib.sh"

t::run "all-pass case finishes with exit 0" '
  ( source "$REPO_ROOT/audit/lib/assert.sh"
    local tmp; tmp="$(mktemp -d)"
    ln -s /tmp/nowhere "$tmp/link"
    assert_symlink_exists "$tmp/link"
    assert_symlink_target "$tmp/link" "/tmp/nowhere"
    assert_no_symlink     "$tmp/missing"
    assert_exit_code 0 -- true
    echo hello > "$tmp/file"
    assert_file_contains  "$tmp/file" "hello"
    rm -rf "$tmp"
    assertions::finish
  )
'

t::run "one-fail case exits non-zero but reports all results" '
  local out rc
  out="$( ( source "$REPO_ROOT/audit/lib/assert.sh"
            assert_exit_code 0 -- true     # pass
            assert_exit_code 0 -- false    # fail
            assert_exit_code 0 -- true     # pass — must still run
            assertions::finish ) 2>&1 || true )"
  rc=$?
  t::assert "third assertion ran" "[[ \"$out\" == *3* ]]"
  t::assert "summary mentions failure" "[[ \"$out\" == *FAIL* || \"$out\" == *failed* ]]"
'

t::summary
```

- [ ] **Step 2: Run to confirm failure**

Run: `bash tests/audit/test_assert.sh`
Expected: source error.

- [ ] **Step 3: Write `audit/lib/assert.sh`**

```bash
# audit/lib/assert.sh — accumulating assertions for audit demo scripts.
#
# Each helper records a pass/fail line. `assertions::finish` prints a
# summary and exits non-zero if any assertion failed.

ASSERT_PASS=0
ASSERT_FAIL=0
ASSERT_LOG=""

_assert_record() {
  local ok="$1" desc="$2"
  if [ "$ok" = "1" ]; then
    ASSERT_PASS=$((ASSERT_PASS + 1))
    ASSERT_LOG="${ASSERT_LOG}PASS  ${desc}
"
  else
    ASSERT_FAIL=$((ASSERT_FAIL + 1))
    ASSERT_LOG="${ASSERT_LOG}FAIL  ${desc}
"
  fi
}

assert_symlink_exists() {
  local path="$1"
  if [ -L "$path" ]; then _assert_record 1 "symlink exists: $path"
  else                    _assert_record 0 "symlink exists: $path"
  fi
}

assert_no_symlink() {
  local path="$1"
  if [ -L "$path" ] || [ -e "$path" ]; then _assert_record 0 "no symlink at: $path"
  else                                       _assert_record 1 "no symlink at: $path"
  fi
}

assert_symlink_target() {
  local path="$1" expected="$2" actual=""
  if [ -L "$path" ]; then actual="$(readlink "$path")"; fi
  if [ "$actual" = "$expected" ]; then
    _assert_record 1 "symlink $path -> $expected"
  else
    _assert_record 0 "symlink $path -> $expected (got: $actual)"
  fi
}

assert_file_contains() {
  local path="$1" needle="$2"
  if [ -f "$path" ] && grep -qF -- "$needle" "$path"; then
    _assert_record 1 "file contains '$needle': $path"
  else
    _assert_record 0 "file contains '$needle': $path"
  fi
}

# assert_exit_code EXPECTED -- cmd [args...]
assert_exit_code() {
  local expected="$1"; shift
  if [ "$1" != "--" ]; then
    _assert_record 0 "assert_exit_code: missing '--' separator"
    return
  fi
  shift
  local rc=0
  "$@" >/dev/null 2>&1 || rc=$?
  if [ "$rc" = "$expected" ]; then
    _assert_record 1 "exit $expected: $*"
  else
    _assert_record 0 "exit $expected: $* (got: $rc)"
  fi
}

assertions::finish() {
  printf '\n%s' "$ASSERT_LOG"
  printf '\n%d PASS · %d FAIL\n' "$ASSERT_PASS" "$ASSERT_FAIL"
  [ "$ASSERT_FAIL" -eq 0 ]
}
```

- [ ] **Step 4: Run test, confirm pass**

Run: `bash tests/audit/test_assert.sh`
Expected: `2 passed, 0 failed`.

- [ ] **Step 5: Commit**

```bash
git add audit/lib/assert.sh tests/audit/test_assert.sh
git commit -m "feat(audit): accumulating assertions with PASS/FAIL summary"
```

---

## Task 5: Wire shell tests into `pytest`

Existing Python test suite is the canonical gate. Shell tests must run alongside it so they aren't forgotten.

**Files:**
- Modify: `tests/audit/__init__.py` (create as empty)
- Create: `tests/audit/test_shell_tests.py`

- [ ] **Step 1: Create the test that invokes each shell test**

Create `tests/audit/__init__.py` (empty file).

Create `tests/audit/test_shell_tests.py`:

```python
"""Wraps each audit/ shell test as a pytest case so CI runs them all."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
SHELL_TESTS = sorted(HERE.glob("test_*.sh"))


@pytest.mark.parametrize("script", SHELL_TESTS, ids=lambda p: p.name)
def test_audit_shell_test(script: Path) -> None:
    result = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"{script.name} failed (rc={result.returncode})\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}\n"
        )
```

- [ ] **Step 2: Run pytest, confirm shell tests show up and pass**

Run: `uv run pytest tests/audit/ -v`
Expected: at least 4 parametrized cases (`test_lib.sh`, `test_sandbox.sh`, `test_narrate.sh`, `test_assert.sh`), all PASS.

- [ ] **Step 3: Run full test suite, confirm no regression**

Run: `uv run pytest -q`
Expected: all existing tests still pass; new ones added.

- [ ] **Step 4: Commit**

```bash
git add tests/audit/__init__.py tests/audit/test_shell_tests.py
git commit -m "test(audit): wire shell tests into pytest via subprocess wrapper"
```

---

## Task 6: Companion PR — `demo-hook` in toolkit repo

Switch to the toolkit repo for Tasks 6 and 7. Land them as a single PR before fanning out beyond `skill × claude`.

**Files (in `~/GitHub/agent-toolkit/`):**
- Create: `hooks/demo-hook.meta.yaml`
- Create: `hooks/demo-hook.sh`

- [ ] **Step 1: Create a worktree in the toolkit repo**

```bash
cd ~/GitHub/agent-toolkit
git worktree add ".worktrees/audit-demos-$(date +%s)" -b audit-demos
cd .worktrees/audit-demos-*
```

- [ ] **Step 2: Write the metadata sidecar**

Create `hooks/demo-hook.meta.yaml`:

```yaml
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: demo-hook
  description: Demo hook for cross-harness verification. Fires on PreToolUse for the Bash tool and prints a single marker line. Used by the agent-toolkit audit process.
  lifecycle: experimental
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - claude
  hook:
    events:
      - PreToolUse
    matcher: Bash
    command: '{HOOKS_DIR}/demo-hook.sh'
```

- [ ] **Step 3: Write the hook script**

Create `hooks/demo-hook.sh`:

```bash
#!/usr/bin/env bash
# demo-hook.sh — fires on PreToolUse for Bash and emits a marker.
# Stdin (hook payload JSON) is intentionally ignored; this is purely an
# audit fixture.
printf '🟧 DEMO-HOOK FIRED — PreToolUse:Bash\n' >&2
exit 0
```

Make it executable:

```bash
chmod +x hooks/demo-hook.sh
```

- [ ] **Step 4: Validate**

Run: `agent-toolkit-cli --toolkit-repo "$PWD" check --exit-code`
Expected: exit code 0; no schema violations.

- [ ] **Step 5: Commit**

```bash
git add hooks/demo-hook.meta.yaml hooks/demo-hook.sh
git commit -m "feat(hooks): add demo-hook for audit-process cross-harness verification"
```

---

## Task 7: Companion PR — `demo-pi-extension` in toolkit repo

**Files (in `~/GitHub/agent-toolkit/`):**
- Create: `extensions/demo-pi-extension/extension.meta.yaml`
- Create: `extensions/demo-pi-extension/index.ts`
- Create: `extensions/demo-pi-extension/package.json`

- [ ] **Step 1: Write the metadata sidecar**

Create `extensions/demo-pi-extension/extension.meta.yaml`:

```yaml
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: demo-pi-extension
  description: Demo Pi extension for cross-harness verification. Logs a marker line at load time and exposes no functionality. Used by the agent-toolkit audit process.
  lifecycle: experimental
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - pi
```

- [ ] **Step 2: Write the extension body**

Create `extensions/demo-pi-extension/index.ts`:

```typescript
// demo-pi-extension — audit fixture. Logs once on load; does nothing else.
console.log("🟪 DEMO-PI-EXTENSION LOADED");
export default {};
```

Create `extensions/demo-pi-extension/package.json`:

```json
{
  "name": "demo-pi-extension",
  "version": "0.0.1",
  "private": true,
  "main": "index.ts",
  "description": "Demo Pi extension for agent-toolkit audit-process verification."
}
```

- [ ] **Step 3: Validate**

Run: `agent-toolkit-cli --toolkit-repo "$PWD" check --exit-code`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add extensions/demo-pi-extension/
git commit -m "feat(extensions): add demo-pi-extension for audit-process verification"
```

- [ ] **Step 5: Push and open the companion PR**

```bash
git push -u origin audit-demos
gh pr create --title "feat: demo-hook + demo-pi-extension for audit-process" --body "$(cat <<'EOF'
## Summary
- Adds `hooks/demo-hook` (Bash PreToolUse marker hook, claude-only).
- Adds `extensions/demo-pi-extension` (Pi-only marker extension).
- Both are first-party audit fixtures; consumed by the `agent-toolkit-cli` audit-process work.

## Test plan
- [x] `agent-toolkit-cli check --exit-code` passes on the toolkit repo.
EOF
)"
```

- [ ] **Step 6: Switch back to the CLI repo worktree**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/audit-process-*
```

(The remaining tasks proceed without waiting for the companion PR to merge — the demos in tasks 8+ can be developed against the local branch by setting `AGENT_TOOLKIT_REPO` to point at the companion-PR worktree. We mention this only to unblock parallel work; default execution merges the PR first.)

---

## Task 8: Reference cell — `skill × claude` (skeleton)

**Files:**
- Create: `audit/demos/skill-claude.sh`

This task lands the demo as a self-hosting tmux script with **no body** beyond the re-exec + sandbox + a smoke assertion. The full op-group walk-through arrives in Task 9. Splitting lets us prove the tmux re-exec works before the script gets long.

- [ ] **Step 1: Write the skeleton**

Create `audit/demos/skill-claude.sh`:

```bash
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

step "skill × claude — smoke check (skeleton)"
run "echo HOME=$HOME"
run "echo AGENT_TOOLKIT_REPO=$AGENT_TOOLKIT_REPO"

# Smoke: a fresh sandbox HOME is a real directory and AGENT_TOOLKIT_REPO
# points at something with a skills/ folder.
assert_exit_code 0 -- test -d "$HOME"
assert_exit_code 0 -- test -d "$AGENT_TOOLKIT_REPO/skills"

assertions::finish
rc=$?
# Hold the pane so the human can see results after attach.
read -rp "press Enter to close" _ || true
exit "$rc"
```

```bash
chmod +x audit/demos/skill-claude.sh
```

- [ ] **Step 2: Headless smoke test (no tmux attach)**

Run: `PAUSE_SCALE=0 AUDIT_INSIDE_TMUX=1 bash audit/demos/skill-claude.sh < /dev/null`
Expected: ends with `2 PASS · 0 FAIL` and exit 0. (The `read` falls through immediately because stdin is closed.)

- [ ] **Step 3: Verify the tmux spawn path prints the attach command**

Run: `bash audit/demos/skill-claude.sh`
Expected: prints `tmux attach -t audit-skill-claude` and exits 0. (You can `tmux attach -t audit-skill-claude` manually to watch it run; press Enter to close.)

Cleanup: `tmux kill-session -t audit-skill-claude 2>/dev/null || true`.

- [ ] **Step 4: Commit**

```bash
git add audit/demos/skill-claude.sh
git commit -m "feat(audit): skill-claude demo skeleton (self-hosting tmux + sandbox smoke)"
```

---

## Task 9: Reference cell — `skill × claude` (full op-group coverage)

Build out the four op groups + robustness scenarios for skill × claude. This is the template the fan-out follows.

**Files:**
- Modify: `audit/demos/skill-claude.sh`

- [ ] **Step 1: Identify the claude skills target dir**

Read `src/agent_toolkit_cli/harness_adapters/claude.py` and confirm: skills project as a symlink at `$CLAUDE_CONFIG_DIR/skills/<slug>` (where `CLAUDE_CONFIG_DIR` defaults to `$HOME/.claude`). Capture the exact path expression for use in the demo — assume `$CLAUDE_CONFIG_DIR/skills/demo-skill` going forward.

- [ ] **Step 2: Rewrite the demo body**

Replace the smoke section in `audit/demos/skill-claude.sh` (everything after `sandbox::init` and before `assertions::finish`) with:

```bash
TARGET="$CLAUDE_CONFIG_DIR/skills/demo-skill/SKILL.md"
LINK_DIR="$CLAUDE_CONFIG_DIR/skills/demo-skill"
EXPECTED_TARGET="$AGENT_TOOLKIT_REPO/skills/demo-skill/SKILL.md"
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
assert_symlink_exists ".claude/skills/demo-skill/SKILL.md"
assert_file_contains  ".agent-toolkit.yaml" "demo-skill"
run "agent-toolkit-cli --project . unlink project claude skill:demo-skill"
assert_no_symlink ".claude/skills/demo-skill/SKILL.md"
cd - >/dev/null

# Re-establish user-scope link so the remaining ops have something to inspect.
run "agent-toolkit-cli link user claude skill:demo-skill"

# ---------- Validation ----------
step "Validation 1/3 — check passes on the projected state"
assert_exit_code 0 -- agent-toolkit-cli --toolkit-repo "$AGENT_TOOLKIT_REPO" check --exit-code
pause 1

step "Validation 2/3 — doctor reports green"
run "agent-toolkit-cli doctor"
assert_exit_code 0 -- agent-toolkit-cli doctor

step "Validation 3/3 — fix is a no-op on a clean state"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" fix"

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
run "agent-toolkit-cli list user claude"

step "Inspection 2/3 — diff"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" diff user claude || true"

step "Inspection 3/3 — inventory"
run "agent-toolkit-cli --toolkit-repo \"$AGENT_TOOLKIT_REPO\" inventory"

# ---------- Human-edit robustness ----------
step "Robustness 1/3 — delete the symlink, re-run link, expect re-creation"
rm -f "$TARGET" && rmdir "$LINK_DIR" 2>/dev/null || true
run "agent-toolkit-cli link user claude skill:demo-skill"
assert_symlink_exists "$TARGET"
assert_symlink_target "$TARGET" "$EXPECTED_TARGET"

step "Robustness 2/3 — edit .agent-toolkit.yaml to drop demo-skill, re-link, expect removal"
python3 -c "import sys,yaml; p='$ALLOWLIST'; d=yaml.safe_load(open(p)); d['skills']=[s for s in (d.get('skills') or []) if s!='demo-skill']; open(p,'w').write(yaml.safe_dump(d))"
run "agent-toolkit-cli link user claude"
assert_no_symlink "$TARGET"

step "Robustness 3/3 — hand-edit the projected file is detected by doctor"
# Restore allowlist + relink first.
run "agent-toolkit-cli link user claude skill:demo-skill"
# Symlinks point at the SSOT, so editing 'the projection' edits the source.
# What we actually probe: replacing the symlink with a regular file (a
# realistic 'human-edit' scenario) — doctor must report drift.
rm "$TARGET"
echo "hand-edited" > "$TARGET"
run "agent-toolkit-cli doctor || true"
# Expectation: doctor exits non-zero. If this assertion fails it's itself
# a finding (doctor is blind to this drift), so we record it but do not
# abort.
assert_exit_code 0 -- bash -c 'agent-toolkit-cli doctor; [ $? -ne 0 ]'
```

- [ ] **Step 3: Headless run, confirm exit 0**

Run: `PAUSE_SCALE=0 AUDIT_INSIDE_TMUX=1 bash audit/demos/skill-claude.sh < /dev/null`
Expected: all assertions PASS (or the robustness 3/3 assertion FAILs, which is itself a documented finding — see the note in step 2). Either way the script's exit code reflects accumulated state; the **goal of this step** is that no assertion fails *unexpectedly*. If something other than the documented robustness gap fails, fix it before committing.

- [ ] **Step 4: Sabotage check — confirm regressions are caught**

Run: `PAUSE_SCALE=0 AUDIT_INSIDE_TMUX=1 bash -c 'set -e; rm -rf "$HOME/.agent-toolkit.yaml" 2>/dev/null; bash audit/demos/skill-claude.sh' < /dev/null`

Actually safer sabotage: temporarily move the demo asset aside.

```bash
mv ~/GitHub/agent-toolkit/skills/demo-skill /tmp/saved-demo-skill
PAUSE_SCALE=0 AUDIT_INSIDE_TMUX=1 bash audit/demos/skill-claude.sh < /dev/null || echo "EXPECTED FAIL: $?"
mv /tmp/saved-demo-skill ~/GitHub/agent-toolkit/skills/demo-skill
```

Expected: exit non-zero (multiple assertion failures listed in the summary).

- [ ] **Step 5: Commit**

```bash
git add audit/demos/skill-claude.sh
git commit -m "feat(audit): skill-claude full op-group coverage (lifecycle/validation/authoring/inspection/robustness)"
```

---

## Task 10: `code_probe.py`

**Files:**
- Create: `audit/lib/code_probe.py`
- Create: `tests/audit/test_code_probe.sh`

- [ ] **Step 1: Write the failing test**

Create `tests/audit/test_code_probe.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib.sh"

OUT="$(uv run --project "$REPO_ROOT" python "$REPO_ROOT/audit/lib/code_probe.py")"

t::run "emits a header line" '
  t::assert "header present" "[[ \"$OUT\" == kind*harness* ]]"
'

t::run "claims skill x claude is supported" '
  t::assert "skill claude line" "[[ \"$OUT\" == *skill\$(printf \\\\t)claude* || \"$OUT\" == *skill*claude* ]]"
'

t::run "claims agent x codex is NOT supported (no slot)" '
  # The line should either be absent, or marked unsupported.
  if printf "%s\n" "$OUT" | awk -F"\t" -v k="agent" -v h="codex" "\$1==k && \$2==h {print \$3}" | grep -q "true"; then
    echo "agent x codex should not be supported" >&2; return 1
  fi
'

t::summary
```

- [ ] **Step 2: Run to confirm failure**

Run: `bash tests/audit/test_code_probe.sh`
Expected: error (`code_probe.py` doesn't exist).

- [ ] **Step 3: Write `audit/lib/code_probe.py`**

```python
"""code_probe.py — emit (kind, harness, supported) TSV from CLI internals.

Imports `agent_toolkit_cli.commands.link` (or whichever module owns the
authoritative (harness, kind) → target_dir table) and prints one TSV line
per pair. Output format: `kind\\tharness\\tsupported` where supported is
`true` or `false`. A header line precedes the data.

This is the **code-derived** probe in the audit's three-source support
matrix. Schema and empirical probes live in audit/discover-matrix.sh.
"""
from __future__ import annotations

import sys

# Kinds and harnesses the audit cares about. Mirrors the schema enum;
# the schema probe will compare against this.
KINDS = ["skill", "agent", "command", "hook", "mcp", "plugin", "pi-extension"]
HARNESSES = ["claude", "codex", "opencode", "gemini", "pi"]


def _supported(kind: str, harness: str) -> bool:
    """Ask the CLI: can `link <harness> <kind>:<x>` produce anything?

    Strategy:
    1. Try to import a target-dir table from the link command. If a (harness, kind)
       cell maps to a real path, it's supported.
    2. Fall back to harness_adapters introspection for MCP/hook strategies.
    """
    # Import locally so the script remains useful even before the package
    # is installed in dev mode (uv run handles editable install).
    from agent_toolkit_cli.commands import link as link_mod  # noqa: PLC0415

    # The CLI exposes the table differently in different versions. Try a
    # few known locations in order; each raises AttributeError on miss.
    table = (
        getattr(link_mod, "HARNESS_TARGET_DIR", None)
        or getattr(link_mod, "harness_target_dir", None)
    )
    if table is None:
        # As of the audit-process spec date, the table lives inline in
        # link.py. Re-discover by reading the source path map.
        from agent_toolkit_cli.harness_adapters import (  # noqa: PLC0415
            claude,
            codex,
            opencode,
            gemini,
            pi,
        )
        # Adapter modules expose per-kind slot constants where supported.
        # Absence ≡ unsupported.
        adapters = {
            "claude": claude,
            "codex": codex,
            "opencode": opencode,
            "gemini": gemini,
            "pi": pi,
        }
        mod = adapters.get(harness)
        if mod is None:
            return False
        # Convention: `SLOTS: dict[str, str]` mapping kind → relative path.
        slots = getattr(mod, "SLOTS", None)
        if isinstance(slots, dict):
            return kind in slots
        # Fall back: any attribute named e.g. `SKILLS_DIR` indicates support.
        attr = f"{kind.replace('-', '_').upper()}S_DIR"
        return hasattr(mod, attr)

    return (harness, kind) in table


def main() -> int:
    print("kind\tharness\tsupported")
    for kind in KINDS:
        for harness in HARNESSES:
            ok = "true" if _supported(kind, harness) else "false"
            print(f"{kind}\t{harness}\t{ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the probe directly, verify TSV shape**

Run: `uv run python audit/lib/code_probe.py | head -5`
Expected: header + four rows of `kind\tharness\ttrue|false`.

- [ ] **Step 5: Run the shell test, confirm pass**

Run: `bash tests/audit/test_code_probe.sh`
Expected: `3 passed, 0 failed`.

- [ ] **Step 6: If the assertion in step 5 fails because the introspection strategy doesn't match the codebase**

The fallback chain in `_supported` covers two known patterns. If both miss, **stop and investigate**: read `src/agent_toolkit_cli/commands/link.py` and the relevant adapter file, find the authoritative table, add a new branch to `_supported` that reads it directly. Do not "fix" the test to match a wrong probe — the whole point is that the probe reflects what the CLI actually does.

- [ ] **Step 7: Commit**

```bash
git add audit/lib/code_probe.py tests/audit/test_code_probe.sh
git commit -m "feat(audit): code_probe.py — emit (kind,harness,supported) TSV from CLI internals"
```

---

## Task 11: `discover-matrix.sh` — schema + empirical probes

**Files:**
- Create: `audit/discover-matrix.sh`
- Create: `tests/audit/test_discover_matrix.sh`

- [ ] **Step 1: Write the failing test**

Create `tests/audit/test_discover_matrix.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib.sh"

OUT="$(bash "$REPO_ROOT/audit/discover-matrix.sh" --no-empirical)"

t::run "emits header" '
  t::assert "header" "[[ \"$OUT\" == kind*harness*source*supported* ]]"
'

t::run "covers all three sources" '
  t::assert "has code rows"      "[[ \"$OUT\" == *code* ]]"
  t::assert "has schema rows"    "[[ \"$OUT\" == *schema* ]]"
'

t::summary
```

- [ ] **Step 2: Run to confirm failure**

Run: `bash tests/audit/test_discover_matrix.sh`
Expected: error (script missing).

- [ ] **Step 3: Write `audit/discover-matrix.sh`**

```bash
#!/usr/bin/env bash
# audit/discover-matrix.sh — emit the support matrix as 4-col TSV.
#
# Output:  kind \t harness \t source \t supported
# Sources: code | schema | empirical
#
# Flags:
#   --no-empirical   skip the empirical probe (faster, used in tests).

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"

DO_EMPIRICAL=1
for arg in "$@"; do
  case "$arg" in
    --no-empirical) DO_EMPIRICAL=0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

SCHEMA="$REPO_ROOT/src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json"

printf 'kind\tharness\tsource\tsupported\n'

# --- code ---
uv run --project "$REPO_ROOT" python "$REPO_ROOT/audit/lib/code_probe.py" \
  | awk -F'\t' 'NR>1 { printf "%s\t%s\tcode\t%s\n", $1, $2, $3 }'

# --- schema ---
# The schema enumerates kinds and harnesses globally; an individual asset
# declares spec.harnesses. For the matrix we ask: "does the schema permit
# (kind, harness)?" — i.e. does the harness appear in the global enum?
# The intersection per kind is enforced per-asset, not in the schema, so
# the schema's answer for every (kind, harness) where harness is in the
# global enum is `true`. This will disagree with code/empirical for cells
# the CLI hasn't implemented yet — which is the point.
KINDS=$(jq -r '.. | objects | .properties.kind?.enum // empty | .[]' "$SCHEMA" 2>/dev/null | sort -u)
HARNESSES=$(jq -r '.. | objects | .properties.harnesses?.items?.enum // empty | .[]' "$SCHEMA" 2>/dev/null | sort -u)

# Fall back to known sets if the jq query returns nothing (schema structure
# may evolve). Mirrors the lists in code_probe.py.
if [ -z "$KINDS" ]; then
  KINDS=$'skill\nagent\ncommand\nhook\nmcp\nplugin\npi-extension'
fi
if [ -z "$HARNESSES" ]; then
  HARNESSES=$'claude\ncodex\nopencode\ngemini\npi'
fi

while IFS= read -r k; do
  [ -z "$k" ] && continue
  while IFS= read -r h; do
    [ -z "$h" ] && continue
    printf '%s\t%s\tschema\ttrue\n' "$k" "$h"
  done <<< "$HARNESSES"
done <<< "$KINDS"

# --- empirical ---
if [ "$DO_EMPIRICAL" -eq 0 ]; then
  exit 0
fi

source "$REPO_ROOT/audit/lib/sandbox.sh"

# For each (kind, harness) the code probe claims supported, attempt a link
# in a fresh sandbox and check whether a file/symlink materialized under
# the harness's projection root.
uv run --project "$REPO_ROOT" python "$REPO_ROOT/audit/lib/code_probe.py" \
  | awk -F'\t' 'NR>1 && $3=="true" { print $1"\t"$2 }' \
  | while IFS=$'\t' read -r kind harness; do
      ( sandbox::init
        slug="demo-${kind}"
        # Convert pi-extension demo slug correctly.
        case "$kind" in
          pi-extension) slug="demo-pi-extension" ;;
        esac
        if agent-toolkit-cli link user "$harness" "${kind}:${slug}" >/dev/null 2>&1; then
          # Count any non-empty harness config dir as evidence.
          case "$harness" in
            claude)   probe_dir="$CLAUDE_CONFIG_DIR" ;;
            codex)    probe_dir="$CODEX_HOME" ;;
            *)        probe_dir="$HOME" ;;
          esac
          if find "$probe_dir" -name "*${slug}*" -print -quit 2>/dev/null | grep -q .; then
            printf '%s\t%s\tempirical\ttrue\n' "$kind" "$harness"
          else
            printf '%s\t%s\tempirical\tfalse\n' "$kind" "$harness"
          fi
        else
          printf '%s\t%s\tempirical\tfalse\n' "$kind" "$harness"
        fi
      )
    done
```

```bash
chmod +x audit/discover-matrix.sh
```

- [ ] **Step 4: Run test, confirm pass**

Run: `bash tests/audit/test_discover_matrix.sh`
Expected: `2 passed, 0 failed`.

- [ ] **Step 5: Run with the empirical probe to confirm it terminates**

Run: `bash audit/discover-matrix.sh | wc -l`
Expected: a number > 50 (kinds × harnesses × 3 sources, minus the empirical-false skips). Should finish in under 30 seconds.

- [ ] **Step 6: Commit**

```bash
git add audit/discover-matrix.sh tests/audit/test_discover_matrix.sh
git commit -m "feat(audit): discover-matrix.sh — three-source support TSV"
```

---

## Task 12: `build-doc.sh` — initial scaffold

This task lands `build-doc.sh` producing a fresh doc from scratch. Idempotent merge of existing prose comes in Task 13.

**Files:**
- Create: `audit/build-doc.sh`
- Create: `tests/audit/test_build_doc.sh`

- [ ] **Step 1: Write the failing test**

Create `tests/audit/test_build_doc.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib.sh"

TMPDOC="$(mktemp)"
bash "$REPO_ROOT/audit/build-doc.sh" --out "$TMPDOC" --no-empirical

t::run "produces a Toolkit Audit document" '
  t::assert "title present"    "grep -q \"# Toolkit Audit\" \"$TMPDOC\""
  t::assert "rollup section"   "grep -q \"## Rollup\" \"$TMPDOC\""
  t::assert "matrix section"   "grep -q \"## Support matrix\" \"$TMPDOC\""
  t::assert "cells section"    "grep -q \"## Cells\" \"$TMPDOC\""
'

t::run "embeds a code-derived matrix table" '
  t::assert "Code-derived heading" "grep -q \"### Code-derived\" \"$TMPDOC\""
'

t::run "creates cell stubs for supported cells" '
  t::assert "skill x claude stub" "grep -q \"### skill × claude\" \"$TMPDOC\""
  t::assert "skill x claude marker" "grep -q \"BEGIN_AUDIT:cell skill-claude\" \"$TMPDOC\""
'

rm -f "$TMPDOC"
t::summary
```

- [ ] **Step 2: Run to confirm failure**

Run: `bash tests/audit/test_build_doc.sh`
Expected: error (script missing).

- [ ] **Step 3: Write `audit/build-doc.sh`**

```bash
#!/usr/bin/env bash
# audit/build-doc.sh — scaffold/merge docs/audit/<date>-toolkit-audit.md.
#
# Flags:
#   --out PATH         output path (default: docs/audit/YYYY-MM-DD-toolkit-audit.md
#                                            using today's date)
#   --no-empirical     pass-through to discover-matrix.sh

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"

OUT=""
EXTRA_FLAGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --no-empirical) EXTRA_FLAGS+=(--no-empirical); shift ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$OUT" ]; then
  OUT="$REPO_ROOT/docs/audit/$(date +%F)-toolkit-audit.md"
  mkdir -p "$(dirname "$OUT")"
fi

TSV="$(bash "$REPO_ROOT/audit/discover-matrix.sh" "${EXTRA_FLAGS[@]}")"

render_matrix() {
  local src="$1" label="$2"
  printf '### %s\n\n' "$label"
  # All distinct kinds and harnesses present in the TSV.
  local kinds harnesses
  kinds=$(printf '%s\n' "$TSV"  | awk -F'\t' -v s="$src" 'NR>1 && $3==s {print $1}' | sort -u)
  harnesses=$(printf '%s\n' "$TSV" | awk -F'\t' -v s="$src" 'NR>1 && $3==s {print $2}' | sort -u)
  # Header row.
  printf '|         |'
  while IFS= read -r h; do [ -n "$h" ] && printf ' %s |' "$h"; done <<< "$harnesses"
  printf '\n|---------|'
  while IFS= read -r h; do [ -n "$h" ] && printf ':---:|'; done <<< "$harnesses"
  printf '\n'
  # Data rows.
  while IFS= read -r k; do
    [ -z "$k" ] && continue
    printf '| %s |' "$k"
    while IFS= read -r h; do
      [ -z "$h" ] && continue
      local supported
      supported=$(printf '%s\n' "$TSV" | awk -F'\t' -v s="$src" -v k="$k" -v h="$h" \
                  'NR>1 && $3==s && $1==k && $2==h {print $4; exit}')
      case "$supported" in
        true)  printf ' ✓ |' ;;
        false) printf ' — |' ;;
        *)     printf '   |' ;;
      esac
    done <<< "$harnesses"
    printf '\n'
  done <<< "$kinds"
  printf '\n'
}

render_disagreements() {
  printf '### Disagreements\n\n'
  local pairs
  pairs=$(printf '%s\n' "$TSV" | awk -F'\t' 'NR>1 {print $1"\t"$2}' | sort -u)
  local any=0
  while IFS=$'\t' read -r k h; do
    [ -z "$k" ] && continue
    local c s e
    c=$(printf '%s\n' "$TSV" | awk -F'\t' -v k="$k" -v h="$h" '$1==k && $2==h && $3=="code"      {print $4}')
    s=$(printf '%s\n' "$TSV" | awk -F'\t' -v k="$k" -v h="$h" '$1==k && $2==h && $3=="schema"    {print $4}')
    e=$(printf '%s\n' "$TSV" | awk -F'\t' -v k="$k" -v h="$h" '$1==k && $2==h && $3=="empirical" {print $4}')
    # Empty empirical (when --no-empirical was used) is not a disagreement.
    if [ -z "$e" ]; then
      [ "$c" != "$s" ] && { printf -- '- %s × %s: code=%s, schema=%s\n' "$k" "$h" "$c" "$s"; any=1; }
    else
      if [ "$c" != "$s" ] || [ "$c" != "$e" ] || [ "$s" != "$e" ]; then
        printf -- '- %s × %s: code=%s, schema=%s, empirical=%s\n' "$k" "$h" "$c" "$s" "$e"
        any=1
      fi
    fi
  done <<< "$pairs"
  if [ "$any" -eq 0 ]; then printf -- '- (none)\n'; fi
  printf '\n'
}

render_cell_stub() {
  local kind="$1" harness="$2"
  cat <<EOF
### ${kind} × ${harness}

<!-- BEGIN_AUDIT:cell ${kind}-${harness} -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — \`audit/demos/${kind}-${harness}.sh\` (\`tmux attach -t audit-${kind}-${harness}\`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell ${kind}-${harness} -->

EOF
}

{
  printf '# Toolkit Audit — %s\n\n' "$(date +%F)"

  printf '## Rollup\n\n'
  printf '<!-- BEGIN_AUDIT:rollup -->\n'
  printf 'Last scaffolded: %s\n\n' "$(date -u +%FT%TZ)"
  printf '_Prioritized issues list — hand-curate below._\n'
  printf '<!-- END_AUDIT:rollup -->\n\n'

  printf '## Support matrix\n\n'
  printf '<!-- BEGIN_AUDIT:matrix -->\n'
  render_matrix code      'Code-derived'
  render_matrix schema    'Schema-derived'
  render_matrix empirical 'Empirical'
  render_disagreements
  printf '<!-- END_AUDIT:matrix -->\n\n'

  printf '## Cells\n\n'
  # Supported = code says true. (Empirical disagreements surface above.)
  printf '%s\n' "$TSV" | awk -F'\t' '$3=="code" && $4=="true" {print $1"\t"$2}' \
    | sort -u | while IFS=$'\t' read -r k h; do
        render_cell_stub "$k" "$h"
      done
} > "$OUT"

printf 'wrote %s\n' "$OUT"
```

```bash
chmod +x audit/build-doc.sh
```

- [ ] **Step 4: Run test, confirm pass**

Run: `bash tests/audit/test_build_doc.sh`
Expected: `3 passed, 0 failed`.

- [ ] **Step 5: Generate the real doc**

Run: `bash audit/build-doc.sh --no-empirical`
Expected: writes `docs/audit/<today>-toolkit-audit.md`. Open it; verify structure matches §10 of the spec.

- [ ] **Step 6: Commit**

```bash
git add audit/build-doc.sh tests/audit/test_build_doc.sh "docs/audit/$(date +%F)-toolkit-audit.md"
git commit -m "feat(audit): build-doc.sh scaffolds findings doc from matrix TSV"
```

---

## Task 13: `build-doc.sh` — idempotent merge

Re-running `build-doc.sh` must preserve hand-edited cell prose. New cells get fresh stubs; cells that no longer appear in the matrix gain a deprecation banner; the rollup's prioritized-issues block is preserved between its own markers.

**Files:**
- Modify: `audit/build-doc.sh`
- Modify: `tests/audit/test_build_doc.sh`

- [ ] **Step 1: Extend the test**

Append to `tests/audit/test_build_doc.sh` (before `t::summary`):

```bash
t::run "second run preserves hand-edited cell prose" '
  local doc; doc="$(mktemp)"
  bash "$REPO_ROOT/audit/build-doc.sh" --out "$doc" --no-empirical
  # Inject hand-edited content into the skill-claude cell.
  perl -i -pe "s|_hand-fill_|MY HAND-WRITTEN PROSE| if /BEGIN_AUDIT:cell skill-claude/ ... /END_AUDIT:cell skill-claude/" "$doc"
  grep -q "MY HAND-WRITTEN PROSE" "$doc" || { echo "setup failed: hand-edit not present" >&2; return 1; }
  # Second run.
  bash "$REPO_ROOT/audit/build-doc.sh" --out "$doc" --no-empirical
  t::assert "hand-written prose preserved" "grep -q \"MY HAND-WRITTEN PROSE\" \"$doc\""
  rm -f "$doc"
'

t::run "second run preserves the rollup hand-curated list" '
  local doc; doc="$(mktemp)"
  bash "$REPO_ROOT/audit/build-doc.sh" --out "$doc" --no-empirical
  perl -i -pe "s|_Prioritized issues list — hand-curate below._|- ISSUE-1: MY ROLLUP NOTE|" "$doc"
  bash "$REPO_ROOT/audit/build-doc.sh" --out "$doc" --no-empirical
  t::assert "rollup note preserved" "grep -q \"MY ROLLUP NOTE\" \"$doc\""
  rm -f "$doc"
'
```

- [ ] **Step 2: Run test, confirm failures**

Run: `bash tests/audit/test_build_doc.sh`
Expected: the two new cases FAIL — second run overwrites prose.

- [ ] **Step 3: Refactor `audit/build-doc.sh` to merge**

Replace the final block of `audit/build-doc.sh` (everything from `printf '## Cells\n\n'` onward) with code that:

1. If `$OUT` already exists, extracts the content between each existing `BEGIN_AUDIT:cell <id>` / `END_AUDIT:cell <id>` marker pair into an associative array keyed by `<id>`. Likewise extract the rollup region.
2. Renders the matrix region from scratch (overwrite).
3. For the rollup region: if the existing region had a non-default hand-curated body, re-use it; otherwise emit the default.
4. For each supported cell: if the cell ID already had a body, splice the old body in between fresh `BEGIN_AUDIT:cell .../END_AUDIT:cell ...` markers (keep markers idempotent, body sacred). If the cell is new, emit the stub. If a cell exists in the file but not in the new matrix, prepend `⚠️ NO LONGER SUPPORTED — review and remove` inside its body and keep it.

The simplest implementation is to keep the same generation pipeline but, immediately before writing `$OUT`, run a small Python helper that does the splice. Add this script inline (a heredoc) — no new file:

```bash
# Inside build-doc.sh, replace the final `{ ... } > "$OUT"` block:
TMP_NEW="$(mktemp)"
{
  # … the same Markdown emission as Task 12, writing the fresh full doc …
} > "$TMP_NEW"

if [ -f "$OUT" ]; then
  python3 - "$OUT" "$TMP_NEW" "$OUT" <<'PYEOF'
import re, sys, pathlib

old_path, new_path, out_path = map(pathlib.Path, sys.argv[1:4])
old = old_path.read_text()
new = new_path.read_text()

def extract_regions(text, prefix):
    """Return dict of region_id -> body, plus the set of seen ids."""
    pat = re.compile(
        rf"<!-- BEGIN_AUDIT:{prefix} ([^ ]+) -->\n(.*?)<!-- END_AUDIT:{prefix} \1 -->",
        re.DOTALL,
    )
    return {m.group(1): m.group(2) for m in pat.finditer(text)}

def extract_single(text, region):
    pat = re.compile(
        rf"<!-- BEGIN_AUDIT:{region} -->\n(.*?)<!-- END_AUDIT:{region} -->",
        re.DOTALL,
    )
    m = pat.search(text)
    return m.group(1) if m else None

old_cells = extract_regions(old, "cell")
new_cells = extract_regions(new, "cell")
old_rollup = extract_single(old, "rollup")

# Splice cell bodies.
def splice_cells(text):
    def repl(m):
        cell_id = m.group(1)
        if cell_id in old_cells:
            return f"<!-- BEGIN_AUDIT:cell {cell_id} -->\n{old_cells[cell_id]}<!-- END_AUDIT:cell {cell_id} -->"
        return m.group(0)
    return re.sub(
        r"<!-- BEGIN_AUDIT:cell ([^ ]+) -->\n.*?<!-- END_AUDIT:cell \1 -->",
        repl, text, flags=re.DOTALL,
    )

result = splice_cells(new)

# Splice rollup body if the user customized it (i.e. it differs from default).
default_marker = "_Prioritized issues list — hand-curate below._"
if old_rollup is not None and default_marker not in old_rollup:
    result = re.sub(
        r"<!-- BEGIN_AUDIT:rollup -->\n.*?<!-- END_AUDIT:rollup -->",
        f"<!-- BEGIN_AUDIT:rollup -->\n{old_rollup}<!-- END_AUDIT:rollup -->",
        result, flags=re.DOTALL,
    )

# Deprecated cells: present in old, absent in new — append with banner.
deprecated_ids = set(old_cells) - set(new_cells)
if deprecated_ids:
    banner_block = "\n## Deprecated cells (no longer in support matrix)\n\n"
    for cid in sorted(deprecated_ids):
        banner_block += (
            f"### {cid.replace('-', ' × ', 1)}\n\n"
            f"<!-- BEGIN_AUDIT:cell {cid} -->\n"
            f"⚠️ NO LONGER SUPPORTED — review and remove.\n\n"
            f"{old_cells[cid]}"
            f"<!-- END_AUDIT:cell {cid} -->\n\n"
        )
    result += banner_block

out_path.write_text(result)
PYEOF
else
  mv "$TMP_NEW" "$OUT"
fi
rm -f "$TMP_NEW" 2>/dev/null || true

printf 'wrote %s\n' "$OUT"
```

- [ ] **Step 4: Run test, confirm pass**

Run: `bash tests/audit/test_build_doc.sh`
Expected: `5 passed, 0 failed`.

- [ ] **Step 5: Manual smoke**

```bash
bash audit/build-doc.sh --no-empirical
# Hand-edit a cell in docs/audit/<today>-toolkit-audit.md, e.g. replace
# one _hand-fill_ with "REAL FINDINGS HERE", save.
bash audit/build-doc.sh --no-empirical
grep "REAL FINDINGS HERE" docs/audit/*.md
```
Expected: the hand-edit survives the second scaffold.

- [ ] **Step 6: Commit**

```bash
git add audit/build-doc.sh tests/audit/test_build_doc.sh
git commit -m "feat(audit): idempotent merge — preserve cell prose and rollup notes across reruns"
```

---

## Task 14: `run-all.sh` + pass/fail wiring

**Files:**
- Create: `audit/run-all.sh`
- Modify: `audit/build-doc.sh` — read `audit/.last-run.tsv` to decorate cell headings

- [ ] **Step 1: Write `audit/run-all.sh`**

```bash
#!/usr/bin/env bash
# audit/run-all.sh — run every demo headlessly, record exit codes to TSV.
set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"

OUT="$REPO_ROOT/audit/.last-run.tsv"
printf 'cell\texit_code\tts\n' > "$OUT"

for demo in "$REPO_ROOT"/audit/demos/*.sh; do
  [ -f "$demo" ] || continue
  cell="$(basename "$demo" .sh)"
  rc=0
  PAUSE_SCALE=0 AUDIT_INSIDE_TMUX=1 bash "$demo" < /dev/null > "$REPO_ROOT/audit/.${cell}.log" 2>&1 || rc=$?
  printf '%s\t%d\t%s\n' "$cell" "$rc" "$(date -u +%FT%TZ)" >> "$OUT"
  printf '  %s\t%s\n' "$cell" "$([ "$rc" -eq 0 ] && echo PASS || echo "FAIL($rc)")"
done

printf '\nresults: %s\n' "$OUT"
```

```bash
chmod +x audit/run-all.sh
```

- [ ] **Step 2: Smoke-run on the single existing demo**

Run: `bash audit/run-all.sh`
Expected: one line for `skill-claude` with rc 0; prints `skill-claude  PASS`.

- [ ] **Step 3: Teach `build-doc.sh` to read `.last-run.tsv`**

In `audit/build-doc.sh`, modify `render_cell_stub` so the H3 line reflects last-run status. Replace the `### ${kind} × ${harness}` line with:

```bash
local cell_id="${kind}-${harness}"
local status_glyph="[STALE]"
if [ -f "$REPO_ROOT/audit/.last-run.tsv" ]; then
  local rc
  rc=$(awk -F'\t' -v c="$cell_id" 'NR>1 && $1==c {print $2; exit}' "$REPO_ROOT/audit/.last-run.tsv")
  case "$rc" in
    0)  status_glyph="[PASS]" ;;
    "") status_glyph="[STALE]" ;;
    *)  status_glyph="[FAIL]" ;;
  esac
fi
cat <<EOF
### ${kind} × ${harness} ${status_glyph}
…
```

(Keep the rest of `render_cell_stub` unchanged.)

- [ ] **Step 4: Regenerate doc, confirm decoration**

Run: `bash audit/build-doc.sh --no-empirical && grep "skill × claude" docs/audit/*.md`
Expected: heading includes `[PASS]`.

- [ ] **Step 5: Forced-fail check**

```bash
# Temporarily break the demo to confirm FAIL flows through.
sed -i.bak 's/assert_exit_code 0 -- true/assert_exit_code 0 -- false/' audit/demos/skill-claude.sh
bash audit/run-all.sh || true
bash audit/build-doc.sh --no-empirical
grep "skill × claude \[FAIL\]" docs/audit/*.md
# Restore.
mv audit/demos/skill-claude.sh.bak audit/demos/skill-claude.sh
bash audit/run-all.sh
```

Expected: while the demo is sabotaged, doc shows `[FAIL]`; after restore, back to `[PASS]`.

- [ ] **Step 6: Update `.gitignore` so the log files don't leak**

Add to `.gitignore` (create if absent):

```
audit/.last-run.tsv
audit/.*.log
```

- [ ] **Step 7: Commit**

```bash
git add audit/run-all.sh audit/build-doc.sh .gitignore
git commit -m "feat(audit): run-all.sh + cell-status decoration in build-doc.sh"
```

---

## Task 15: Fan-out — remaining cells

Order: symmetric kinds first across all harnesses, then the asymmetric kinds.

| Order | Cell | Notes |
|---|---|---|
| 1 | `skill × codex` | Forces Codex skill translator path (TOML, prompt translation). |
| 2 | `skill × opencode` | Pure symlink in OpenCode's user dir. |
| 3 | `skill × gemini` | Verify against real Gemini config (see existing spec `2026-05-19-verify-gemini-agent-raw-symlink-against-real-gem-design.md`). |
| 4 | `skill × pi` | Pi user config. |
| 5 | `agent × <each>` | Agents missing in Codex — confirm the silent-skip invariant. |
| 6 | `command × <each>` | |
| 7 | `hook × claude` | Hook is claude-only (per existing `confirm-rm` shape). |
| 8 | `plugin × <each supporting>` | |
| 9 | `mcp × <each>` | Exercises the non-symlink config-file path; this is the most divergent op-group across harnesses. |
| 10 | `pi-extension × pi` | Pi-only. |

For each cell, follow this sub-template (one task per cell):

- [ ] **Step 1: Confirm support**

Run: `bash audit/discover-matrix.sh --no-empirical | grep -E "^${kind}\\t${harness}\\tcode\\ttrue$"`
Expected: line present. If empty, the cell isn't supported — skip and note in the doc.

- [ ] **Step 2: Identify the projection path for this cell**

Read `src/agent_toolkit_cli/harness_adapters/<harness>.py` (or, for MCPs, the relevant adapter under `_mcp_dispatch.py`). Note: the exact env var, target path template, and whether the projection is a symlink, a folder of generated files, or a config-file mutation.

- [ ] **Step 3: Copy `audit/demos/skill-claude.sh` to `audit/demos/<kind>-<harness>.sh`** and adapt:
  - Change the session name to `audit-<kind>-<harness>`.
  - Change the `TARGET`, `LINK_DIR`, `EXPECTED_TARGET` paths.
  - Substitute the demo slug (`demo-<kind>`).
  - For MCP cells: drop `assert_symlink_*` (no symlinks) and switch to `assert_file_contains` against the projected config file.
  - For Codex skill: account for the prompt translation — the projected file may not be the source SKILL.md verbatim; assert against the *translated* content's marker line instead.

- [ ] **Step 4: Headless run, confirm exit 0** (or document the failure as a finding)

Run: `PAUSE_SCALE=0 AUDIT_INSIDE_TMUX=1 bash audit/demos/<kind>-<harness>.sh < /dev/null`

- [ ] **Step 5: Regenerate doc, hand-write the cell's Findings prose**

```bash
bash audit/build-doc.sh --no-empirical
$EDITOR docs/audit/*.md   # fill the new cell's hand-fill blocks
```

- [ ] **Step 6: Commit per cell**

```bash
git add audit/demos/<kind>-<harness>.sh docs/audit/*.md
git commit -m "feat(audit): cell — <kind> × <harness>"
```

Repeat for each cell in the order table above. **Don't batch-commit** — one cell, one commit, so a regression in cell N+1 doesn't shadow cell N.

---

## Task 16: Final integration sweep

- [ ] **Step 1: Run the full audit**

```bash
bash audit/run-all.sh
bash audit/build-doc.sh   # with empirical probe this time
```

- [ ] **Step 2: Hand-write the Rollup**

Open `docs/audit/<today>-toolkit-audit.md`, replace the rollup's `_Prioritized issues list — hand-curate below._` line with the actual prioritized list, harvested from each cell's `❌` and `⚠️` Findings.

- [ ] **Step 3: Run the test suite**

Run: `uv run pytest -q`
Expected: all green (855+ existing + the new shell-test wrappers).

- [ ] **Step 4: Commit the final doc and merge the worktree branch**

```bash
git add docs/audit/
git commit -m "docs(audit): hand-curated rollup + per-cell findings"
git push -u origin audit-process
gh pr create --title "feat: toolkit audit process (helpers + demos + findings doc)" --body "See docs/superpowers/specs/2026-05-19-toolkit-audit-process-design.md"
```

- [ ] **Step 5: After merge — clean up worktrees**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli
git worktree remove .worktrees/audit-process-*
cd /Users/ajanderson/GitHub/agent-toolkit
git worktree remove .worktrees/audit-demos-*
```

---

## Self-review checklist (run after writing — already done)

- **Spec coverage:** §1 → Task 16; §2 (outputs) → Tasks 1–14; §3 (layout) → file map at top; §4 (sandbox) → Task 2; §5 (demo assets) → Tasks 6–7; §6 (narration/assertions) → Tasks 3–4; §7 (tmux) → Task 8; §8 (cell template) → Task 12; §9 (matrix discovery) → Tasks 10–11; §10 (doc lifecycle) → Tasks 12–13; §11 (op coverage) → Task 9; §12 (sequencing) → mirrored 1:1 in task order; §13 (non-goals) → no tasks (correctly).
- **Placeholder scan:** no TBD/TODO; "hand-fill" is the literal contents of new cell stubs, not a plan placeholder.
- **Type consistency:** `assertions::finish` used consistently; `sandbox::init`/`sandbox::cleanup` consistent; flag names (`--no-empirical`, `--out`) consistent across `discover-matrix.sh` and `build-doc.sh`.
- **Fan-out caveat:** Task 15 is intentionally written as a meta-template, since per-cell code is mechanical adaptation of Task 9. Engineer expands one task per cell at execution time.
