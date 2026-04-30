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

@test "link user conventions exits 0" {
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

@test "link user conventions Layer 3 is idempotent" {
  mkdir -p "$HOME/.claude"
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.claude/CONVENTIONS.md" ]
  [ "$(readlink "$HOME/.claude/CONVENTIONS.md")" = "$HOME/.conventions/CONVENTIONS.md" ]
  [ -L "$HOME/.claude/conventions" ]
  [ "$(readlink "$HOME/.claude/conventions")" = "$HOME/.conventions/conventions" ]
}

@test "link user conventions creates all Layer 3 slots when every harness dir exists" {
  mkdir -p "$HOME/.claude" "$HOME/.codex" "$HOME/.config/opencode" "$HOME/.pi/agent"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.claude/CONVENTIONS.md" ]
  [ -L "$HOME/.claude/conventions" ]
  [ -L "$HOME/.codex/AGENTS.md" ]
  [ -L "$HOME/.config/opencode/AGENTS.md" ]
  [ -L "$HOME/.pi/agent/AGENTS.md" ]
  # Confirm the count: 2 Layer 2 + 5 Layer 3 = 7 distinct symlinks
  [ "$(readlink "$HOME/.codex/AGENTS.md")" = "$HOME/.conventions/CONVENTIONS.md" ]
  [ "$(readlink "$HOME/.config/opencode/AGENTS.md")" = "$HOME/.conventions/CONVENTIONS.md" ]
  [ "$(readlink "$HOME/.pi/agent/AGENTS.md")" = "$HOME/.conventions/CONVENTIONS.md" ]
}

@test "unlink user conventions removes Layer 3 only" {
  mkdir -p "$HOME/.claude" "$HOME/.codex"
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ -L "$HOME/.claude/CONVENTIONS.md" ]
  [ -L "$HOME/.codex/AGENTS.md" ]
  [ -L "$HOME/.conventions/CONVENTIONS.md" ]

  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ ! -L "$HOME/.claude/CONVENTIONS.md" ]
  [ ! -L "$HOME/.claude/conventions" ]
  [ ! -L "$HOME/.codex/AGENTS.md" ]
  # Layer 2 must persist
  [ -L "$HOME/.conventions/CONVENTIONS.md" ]
  [ -L "$HOME/.conventions/conventions" ]
}

@test "list user conventions shows the Layer 3 -> Layer 2 -> Layer 1 chain" {
  mkdir -p "$HOME/.claude" "$HOME/.codex"
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"

  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"$HOME/.claude/CONVENTIONS.md"* ]]
  [[ "$output" == *"$HOME/.conventions/CONVENTIONS.md"* ]]
  [[ "$output" == *"$REPO_ROOT/CONVENTIONS.md"* ]]
  [[ "$output" == *"$HOME/.codex/AGENTS.md"* ]]
}

@test "list user conventions handles missing slots gracefully" {
  # No HOME/.claude, no HOME/.codex etc.
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  # No assertion on output content — just must not crash.
}

@test "unlink user conventions does not touch unrelated symlinks at slot paths" {
  mkdir -p "$HOME/.claude"
  # First, establish Layer 2 and Layer 3 normally.
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ -L "$HOME/.claude/CONVENTIONS.md" ]
  [ "$(readlink "$HOME/.claude/CONVENTIONS.md")" = "$HOME/.conventions/CONVENTIONS.md" ]

  # Now replace the Layer-3 symlink to point elsewhere (not Layer 2) — this exercises the
  # target-guard inside conventions_unlink_main.
  rm "$HOME/.claude/CONVENTIONS.md"
  ln -s "$REPO_ROOT/CONVENTIONS.md" "$HOME/.claude/CONVENTIONS.md"  # now points at Layer 1, not Layer 2
  [ "$(readlink "$HOME/.claude/CONVENTIONS.md")" = "$REPO_ROOT/CONVENTIONS.md" ]

  # Unlink should NOT remove this symlink because it doesn't point at Layer 2.
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  # The modified symlink must survive — it is not Layer 2-targeting.
  [ -L "$HOME/.claude/CONVENTIONS.md" ]
  [ "$(readlink "$HOME/.claude/CONVENTIONS.md")" = "$REPO_ROOT/CONVENTIONS.md" ]
}

@test "diff user conventions reports would-link without creating" {
  mkdir -p "$HOME/.claude"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" diff user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"would-link"* ]]
  [ ! -e "$HOME/.conventions/CONVENTIONS.md" ]
  [ ! -e "$HOME/.claude/CONVENTIONS.md" ]
}
