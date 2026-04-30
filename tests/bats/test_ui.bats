#!/usr/bin/env bats

load 'helpers'

setup() {
  HELPER="$BATS_TEST_DIRNAME/../../bin/lib/_ui.sh"
}

@test "_ui_header writes to stderr, not stdout" {
  run bash -c ". $HELPER; _ui_header 'hello' 2>/dev/null"
  [ "$status" -eq 0 ]
  [ -z "$output" ]   # nothing on stdout
}

@test "_ui_header writes the message to stderr" {
  run bash -c ". $HELPER; _ui_header 'hello' 2>&1 >/dev/null"
  [ "$status" -eq 0 ]
  [[ "$output" == *"hello"* ]]
}

@test "_ui_summary writes to stderr" {
  run bash -c ". $HELPER; _ui_summary 'done' 2>&1 >/dev/null"
  [ "$status" -eq 0 ]
  [[ "$output" == *"done"* ]]
}

@test "AGENT_TOOLKIT_QUIET=1 suppresses _ui_header" {
  run bash -c "export AGENT_TOOLKIT_QUIET=1; . $HELPER; _ui_header 'hello' 2>&1 >/dev/null"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "AGENT_TOOLKIT_QUIET=1 suppresses _ui_summary" {
  run bash -c "export AGENT_TOOLKIT_QUIET=1; . $HELPER; _ui_summary 'done' 2>&1 >/dev/null"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
