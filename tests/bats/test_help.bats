#!/usr/bin/env bats

@test "agent-toolkit --help mentions every subcommand" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"link"* ]]
  [[ "$output" == *"unlink"* ]]
  [[ "$output" == *"list"* ]]
  [[ "$output" == *"diff"* ]]
  [[ "$output" == *"check"* ]]
  [[ "$output" == *"fix"* ]]
  [[ "$output" == *"doctor"* ]]
  [[ "$output" == *"new"* ]]
}

@test "agent-toolkit --help has a one-line description per subcommand" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" --help
  [ "$status" -eq 0 ]
  # Each command should have a short explainer alongside its usage.
  [[ "$output" == *"Project assets per"* ]] || [[ "$output" == *"project assets per"* ]]
  [[ "$output" == *"frontmatter"* ]]
  [[ "$output" == *"AGENTS.md"* ]]
}

@test "agent-toolkit with no args prints help (not an error)" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage:"* ]] || [[ "$output" == *"usage:"* ]]
}

@test "help mentions tui subcommand" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"tui"* ]]
}
