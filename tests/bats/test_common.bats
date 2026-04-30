#!/usr/bin/env bats

load 'helpers'

setup() { setup_repo; }
teardown() { teardown_repo; }

@test "common.sh sources without errors" {
  run bash -c "source $BATS_TEST_DIRNAME/../../bin/lib/common.sh; echo OK"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

@test "harness_targets returns target dirs for claude skills" {
  source "$BATS_TEST_DIRNAME/../../bin/lib/common.sh"
  result=$(harness_target_dir claude skill)
  [ "$result" = "$HOME/.claude/skills" ]
}

@test "harness_targets returns empty for unsupported (codex agents)" {
  source "$BATS_TEST_DIRNAME/../../bin/lib/common.sh"
  result=$(harness_target_dir codex agent)
  [ -z "$result" ]
}
