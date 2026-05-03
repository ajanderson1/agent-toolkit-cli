#!/usr/bin/env bats
load 'helpers'

setup() {
  TOOLKIT_ROOT="$BATS_TEST_TMPDIR/toolkit"
  mkdir -p "$TOOLKIT_ROOT/schemas"
  echo '{}' > "$TOOLKIT_ROOT/schemas/asset-frontmatter.v1alpha1.json"
  echo 'tool: agent-toolkit-cli' > "$TOOLKIT_ROOT/.agent-toolkit-source"
  # Canonicalise so equality holds against `pwd -P` output on macOS.
  TOOLKIT_ROOT="$(cd "$TOOLKIT_ROOT" && pwd -P)"

  CLI_BIN="$BATS_TEST_DIRNAME/../../bin/agent-toolkit"
}

@test "resolve_toolkit_root: --toolkit-repo flag wins" {
  run "$CLI_BIN" --resolve-toolkit --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  [ "$output" = "$TOOLKIT_ROOT" ]
}

@test "resolve_toolkit_root: AGENT_TOOLKIT_REPO env" {
  AGENT_TOOLKIT_REPO="$TOOLKIT_ROOT" run "$CLI_BIN" --resolve-toolkit
  [ "$status" -eq 0 ]
  [ "$output" = "$TOOLKIT_ROOT" ]
}

@test "resolve_toolkit_root: walk-up from CWD" {
  mkdir -p "$TOOLKIT_ROOT/skills/foo"
  cd "$TOOLKIT_ROOT/skills/foo"
  unset AGENT_TOOLKIT_REPO
  run "$CLI_BIN" --resolve-toolkit
  [ "$status" -eq 0 ]
  [ "$output" = "$TOOLKIT_ROOT" ]
}

@test "resolve_toolkit_root: fails with helpful message when nothing resolves" {
  mkdir -p "$BATS_TEST_TMPDIR/empty-home"
  cd "$BATS_TEST_TMPDIR/empty-home"
  unset AGENT_TOOLKIT_REPO
  HOME="$BATS_TEST_TMPDIR/empty-home" run "$CLI_BIN" --resolve-toolkit
  [ "$status" -ne 0 ]
  [[ "$output" == *"agent-toolkit"* ]]
  [[ "$output" == *"uv tool install"* ]]
}
