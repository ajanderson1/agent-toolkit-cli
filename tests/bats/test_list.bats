#!/usr/bin/env bats

load 'helpers'

setup() {
  setup_repo
  HOME="$(mktemp -d)"
  export HOME
  mkdir -p "$HOME/.claude/skills"
  mkdir -p "$REPO_ROOT/skills/alpha"
  ln -s "$REPO_ROOT/skills/alpha" "$HOME/.claude/skills/alpha"
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "list user prints existing symlinks pointing into the repo" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list user --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha"* ]]
  [[ "$output" == *"$REPO_ROOT/skills/alpha"* ]]
}

@test "list project prints nothing if .agent-toolkit.yaml is absent" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list project --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
}
