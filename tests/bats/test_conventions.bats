#!/usr/bin/env bats

load 'helpers'

setup() {
  setup_repo
  HOME="$(mktemp -d)"
  export HOME
  # Conventions tree the repo will link from
  mkdir -p "$REPO_ROOT/conventions"
  cat > "$REPO_ROOT/CONVENTIONS.md" <<'EOF'
# CONVENTIONS (test fixture)
EOF
  cat > "$REPO_ROOT/conventions/git.md" <<'EOF'
# git (test fixture)
EOF
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "link user conventions exits 0 (stub)" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
}

@test "link user conventions creates Layer 2 symlinks" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.conventions/CONVENTIONS.md" ]
  [ "$(readlink "$HOME/.conventions/CONVENTIONS.md")" = "$REPO_ROOT/CONVENTIONS.md" ]
  [ -L "$HOME/.conventions/conventions" ]
  [ "$(readlink "$HOME/.conventions/conventions")" = "$REPO_ROOT/conventions" ]
}

@test "link user conventions Layer 2 is idempotent" {
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.conventions/CONVENTIONS.md" ]
  [ "$(readlink "$HOME/.conventions/CONVENTIONS.md")" = "$REPO_ROOT/CONVENTIONS.md" ]
  [ -L "$HOME/.conventions/conventions" ]
  [ "$(readlink "$HOME/.conventions/conventions")" = "$REPO_ROOT/conventions" ]
}

@test "link user conventions refuses to clobber a real file at ~/.conventions/CONVENTIONS.md" {
  mkdir -p "$HOME/.conventions"
  echo "user-content" > "$HOME/.conventions/CONVENTIONS.md"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"refuses to overwrite"* ]]
  [ "$(cat "$HOME/.conventions/CONVENTIONS.md")" = "user-content" ]
}

@test "link user conventions refuses if ~/.conventions exists as a file" {
  echo "user-content" > "$HOME/.conventions"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"refuses to proceed"* ]]
}

@test "link user conventions creates Claude Layer 3 symlinks when ~/.claude exists" {
  mkdir -p "$HOME/.claude"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.claude/CONVENTIONS.md" ]
  [ "$(readlink "$HOME/.claude/CONVENTIONS.md")" = "$HOME/.conventions/CONVENTIONS.md" ]
  [ -L "$HOME/.claude/conventions" ]
  [ "$(readlink "$HOME/.claude/conventions")" = "$HOME/.conventions/conventions" ]
}

@test "link user conventions creates Codex Layer 3 symlink when ~/.codex exists" {
  mkdir -p "$HOME/.codex"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.codex/AGENTS.md" ]
  [ "$(readlink "$HOME/.codex/AGENTS.md")" = "$HOME/.conventions/CONVENTIONS.md" ]
}

@test "link user conventions creates OpenCode Layer 3 symlink when ~/.config/opencode exists" {
  mkdir -p "$HOME/.config/opencode"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.config/opencode/AGENTS.md" ]
  [ "$(readlink "$HOME/.config/opencode/AGENTS.md")" = "$HOME/.conventions/CONVENTIONS.md" ]
}

@test "link user conventions creates Pi Layer 3 symlink when ~/.pi/agent exists" {
  mkdir -p "$HOME/.pi/agent"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.pi/agent/AGENTS.md" ]
  [ "$(readlink "$HOME/.pi/agent/AGENTS.md")" = "$HOME/.conventions/CONVENTIONS.md" ]
}

@test "link user conventions skips harness whose dir does not exist" {
  # Note: setup() creates ONLY a tmp HOME, so ~/.codex etc. do not exist.
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ ! -e "$HOME/.codex/AGENTS.md" ]
  [ ! -e "$HOME/.config/opencode/AGENTS.md" ]
  [ ! -e "$HOME/.pi/agent/AGENTS.md" ]
}
