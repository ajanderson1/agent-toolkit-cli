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

@test "kind_to_section maps every kind correctly" {
  source "$BATS_TEST_DIRNAME/../../bin/lib/common.sh"
  [ "$(kind_to_section skill)" = "skills" ]
  [ "$(kind_to_section agent)" = "agents" ]
  [ "$(kind_to_section command)" = "commands" ]
  [ "$(kind_to_section hook)" = "hooks" ]
  [ "$(kind_to_section plugin)" = "plugins" ]
}

@test "kind_to_section rejects mcp" {
  source "$BATS_TEST_DIRNAME/../../bin/lib/common.sh"
  run kind_to_section mcp
  [ "$status" -ne 0 ]
  [[ "$output" == *"not yet scope-routed"* ]]
}

@test "read_allowlist_section returns slugs from multi-line form" {
  source "$BATS_TEST_DIRNAME/../../bin/lib/common.sh"
  local f="$BATS_TMPDIR/al-$$.yaml"
  cat > "$f" <<'EOF'
skills:
  - alpha
  - beta
agents:
  - scout
EOF
  run read_allowlist_section "$f" skills
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha"* ]]
  [[ "$output" == *"beta"* ]]
  rm -f "$f"
}

@test "read_allowlist_section returns slugs from inline form" {
  source "$BATS_TEST_DIRNAME/../../bin/lib/common.sh"
  local f="$BATS_TMPDIR/al-$$.yaml"
  echo "skills: [alpha, beta]" > "$f"
  run read_allowlist_section "$f" skills
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha"* ]]
  [[ "$output" == *"beta"* ]]
  rm -f "$f"
}

@test "read_allowlist_section is empty for missing file" {
  source "$BATS_TEST_DIRNAME/../../bin/lib/common.sh"
  run read_allowlist_section "$BATS_TMPDIR/no-such-$$.yaml" skills
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "read_allowlist_section strips inline comment in inline form" {
  source "$BATS_TEST_DIRNAME/../../bin/lib/common.sh"
  local f="$BATS_TMPDIR/al-comment-$$.yaml"
  echo "skills: [alpha, beta]   # trailing comment" > "$f"
  run read_allowlist_section "$f" skills
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha"* ]]
  [[ "$output" == *"beta"* ]]
  ! [[ "$output" == *"#"* ]]
  ! [[ "$output" == *"trailing"* ]]
  ! [[ "$output" == *"comment"* ]]
  rm -f "$f"
}

@test "read_allowlist_section ignores nested mappings inside a section" {
  source "$BATS_TEST_DIRNAME/../../bin/lib/common.sh"
  local f="$BATS_TMPDIR/al-nested-$$.yaml"
  cat > "$f" <<'EOF'
skills:
  nested:
    - foo
agents:
  - scout
EOF
  run read_allowlist_section "$f" skills
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  run read_allowlist_section "$f" agents
  [ "$status" -eq 0 ]
  [[ "$output" == *"scout"* ]]
  rm -f "$f"
}

@test "read_allowlist_section handles empty inline form" {
  source "$BATS_TEST_DIRNAME/../../bin/lib/common.sh"
  local f="$BATS_TMPDIR/al-empty-$$.yaml"
  echo "skills: []" > "$f"
  run read_allowlist_section "$f" skills
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  rm -f "$f"
}

@test "read_allowlist_section is empty for missing section in present file" {
  source "$BATS_TEST_DIRNAME/../../bin/lib/common.sh"
  local f="$BATS_TMPDIR/al-missing-section-$$.yaml"
  cat > "$f" <<'EOF'
skills:
  - alpha
EOF
  run read_allowlist_section "$f" agents
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  rm -f "$f"
}
