#!/usr/bin/env bats

load 'helpers'

setup() {
  setup_repo
  HOME="$(mktemp -d)"
  export HOME
  mkdir -p "$HOME/.claude"
  # one claude-only skill
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
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "link user claude creates per-entry symlink for claude-compatible skill" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.claude/skills/alpha" ]
  [ "$(readlink "$HOME/.claude/skills/alpha")" = "$REPO_ROOT/skills/alpha" ]
}

@test "link user claude is idempotent" {
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.claude/skills/alpha" ]
}

@test "link user codex skips skill not tagged for codex" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user codex --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ ! -e "$HOME/.codex/skills/alpha" ]
}

@test "link user claude removes stale symlink when harnesses change" {
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  [ -L "$HOME/.claude/skills/alpha" ]
  # Update the asset to no longer support claude
  sed -i.bak 's/- claude/- codex/' "$REPO_ROOT/skills/alpha/SKILL.md" && rm "$REPO_ROOT/skills/alpha/SKILL.md.bak"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ ! -L "$HOME/.claude/skills/alpha" ]
}

@test "link user claude --dry-run does not create symlink" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT" --dry-run
  [ "$status" -eq 0 ]
  [ ! -e "$HOME/.claude/skills/alpha" ]
  [[ "$output" == *"would-link"* ]]
}
