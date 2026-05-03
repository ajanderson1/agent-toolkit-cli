#!/usr/bin/env bats

load 'helpers'

setup() {
  setup_repo
  HOME="$(mktemp -d)"
  export HOME
  mkdir -p "$HOME/.claude/skills"

  # Symlink the worktree's bin/ into REPO_ROOT so the TUI's CLIRunner —
  # which invokes "$repo_root/bin/agent-toolkit" — finds a working CLI
  # while reading assets out of the test fixture's REPO_ROOT.
  ln -s "$BATS_TEST_DIRNAME/../../bin" "$REPO_ROOT/bin"

  mkdir -p "$REPO_ROOT/skills/alpha"
  cat > "$REPO_ROOT/skills/alpha/SKILL.md" <<'EOF'
---
apiVersion: agent-toolkit/v1alpha1
metadata:
  name: alpha
  description: Alpha skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - claude
---
EOF
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills: []
agents: []
commands: []
hooks: []
plugins: []
EOF
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "tui --headless --apply links a skill end-to-end via real CLI" {
  PLAN="$(mktemp)"
  echo "skill:alpha" > "$PLAN"
  run uv run --project "$BATS_TEST_DIRNAME/../.." agent-toolkit-tui \
        --headless --apply --plan "$PLAN" --scope user --harness claude \
        --op link --repo-root "$REPO_ROOT"
  rm -f "$PLAN"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.claude/skills/alpha" ]
  # Accept either the unresolved or resolved REPO_ROOT path — macOS resolves
  # /var/folders/... to /private/var/folders/... and the runner calls .resolve()
  # before passing --repo-root to the bash CLI, so the symlink target is the
  # physical path. Use `pwd -P` (resolves symlinks) to compute the expected
  # physical path; fall back to the unresolved form on Linux.
  link="$(readlink "$HOME/.claude/skills/alpha")"
  [ "$link" = "$REPO_ROOT/skills/alpha" ] || \
    [ "$link" = "$(cd "$REPO_ROOT" && pwd -P)/skills/alpha" ]
}

@test "tui --headless reports failure for unsupported harness" {
  PLAN="$(mktemp)"
  echo "skill:alpha" > "$PLAN"
  # alpha doesn't declare codex
  run uv run --project "$BATS_TEST_DIRNAME/../.." agent-toolkit-tui \
        --headless --apply --plan "$PLAN" --scope user --harness codex \
        --op link --repo-root "$REPO_ROOT"
  rm -f "$PLAN"
  [ "$status" -eq 1 ]   # 1 = some failed (per CLI grammar)
  [ ! -L "$HOME/.codex/skills/alpha" ]
}
