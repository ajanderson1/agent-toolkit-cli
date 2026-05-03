#!/usr/bin/env bats

load 'helpers'

setup() {
  setup_repo
  HOME="$(mktemp -d)"
  export HOME
  mkdir -p "$TOOLKIT_ROOT/skills/alpha" "$TOOLKIT_ROOT/skills/beta"
  for slug in alpha beta; do
    cat > "$TOOLKIT_ROOT/skills/${slug}/SKILL.md" <<EOF
---
apiVersion: agent-toolkit/v1alpha1
metadata:
  name: ${slug}
  description: ${slug} skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - claude
---
EOF
  done
  # codex-only skill for harness-incompatibility test
  mkdir -p "$TOOLKIT_ROOT/skills/codex-only"
  cat > "$TOOLKIT_ROOT/skills/codex-only/SKILL.md" <<'EOF'
---
apiVersion: agent-toolkit/v1alpha1
metadata:
  name: codex-only
  description: Codex-only skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - codex
---
EOF
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "link user claude skill:alpha creates file and links it" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude skill:alpha --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  [ -f "$HOME/.agent-toolkit.yaml" ]
  grep -q '^[[:space:]]*-[[:space:]]*alpha' "$HOME/.agent-toolkit.yaml"
  [ -L "$HOME/.claude/skills/alpha" ]
}

@test "link user claude skill:alpha then skill:beta keeps both" {
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude skill:alpha --toolkit-repo "$TOOLKIT_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude skill:beta --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  grep -q 'alpha' "$HOME/.agent-toolkit.yaml"
  grep -q 'beta' "$HOME/.agent-toolkit.yaml"
  [ -L "$HOME/.claude/skills/alpha" ]
  [ -L "$HOME/.claude/skills/beta" ]
}

@test "link user claude skill:alpha is idempotent" {
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude skill:alpha --toolkit-repo "$TOOLKIT_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude skill:alpha --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  # Slug appears exactly once
  count=$(grep -c '^[[:space:]]*-[[:space:]]*alpha' "$HOME/.agent-toolkit.yaml")
  [ "$count" -eq 1 ]
  [ -L "$HOME/.claude/skills/alpha" ]
}

@test "link user claude skill:nonexistent errors" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude skill:nonexistent --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"no skill named 'nonexistent'"* ]]
  [ ! -f "$HOME/.agent-toolkit.yaml" ]
}

@test "link user claude skill:codex-only errors with harness incompatibility" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude skill:codex-only --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"doesn't support harness 'claude'"* ]]
  [[ "$output" == *"codex"* ]]
  [ ! -f "$HOME/.agent-toolkit.yaml" ]
}

@test "link user claude mcp:foo errors clearly" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude mcp:foo --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"mcps are not yet scope-routed"* ]]
}

@test "link project claude skill:alpha creates project file in CWD" {
  cd "$TOOLKIT_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link project claude skill:alpha --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  [ -f "$TOOLKIT_ROOT/.agent-toolkit.yaml" ]
  [ -L "$TOOLKIT_ROOT/.claude/skills/alpha" ]
}

@test "link user claude skill:alpha --all errors with mutual-exclusion (slug then --all)" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude skill:alpha --all -y --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"cannot combine --all with"* ]]
}

@test "link user claude skill:alpha --dry-run reports would-link without mutating YAML" {
  run bash -c "'$BATS_TEST_DIRNAME/../../bin/agent-toolkit' link user claude skill:alpha --dry-run --toolkit-repo '$TOOLKIT_ROOT' 2>&1"
  [ "$status" -eq 0 ]
  [[ "$output" == *"would-link"* ]] || [[ "$output" == *"pending"* ]]
  [ ! -f "$HOME/.agent-toolkit.yaml" ]   # the user's file is NOT created under --dry-run
  [ ! -L "$HOME/.claude/skills/alpha" ]
}

@test "link user claude --plan - applies multiple slugs from stdin" {
  run bash -c "printf 'skill:alpha\nskill:beta\n' | '$BATS_TEST_DIRNAME/../../bin/agent-toolkit' link user claude --plan - --toolkit-repo '$TOOLKIT_ROOT'"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.claude/skills/alpha" ]
  [ -L "$HOME/.claude/skills/beta" ]
}

@test "link --plan - ignores comments and blank lines" {
  run bash -c "printf '# this is a comment\n\nskill:alpha\n# trailing comment\n' | '$BATS_TEST_DIRNAME/../../bin/agent-toolkit' link user claude --plan - --toolkit-repo '$TOOLKIT_ROOT'"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.claude/skills/alpha" ]
}

@test "link --plan - reports per-entry failure but continues" {
  run bash -c "printf 'skill:alpha\nskill:does-not-exist\n' | '$BATS_TEST_DIRNAME/../../bin/agent-toolkit' link user claude --plan - --toolkit-repo '$TOOLKIT_ROOT' 2>&1"
  [ "$status" -eq 1 ]   # 1 = some failed
  [ -L "$HOME/.claude/skills/alpha" ]   # the good one still landed
  [[ "$output" == *"does-not-exist"* ]]
}

@test "link --plan - rejects combination with --all" {
  run bash -c "printf '' | '$BATS_TEST_DIRNAME/../../bin/agent-toolkit' link user claude --plan - --all --toolkit-repo '$TOOLKIT_ROOT'"
  [ "$status" -eq 2 ]
}

@test "link --plan - rejects combination with skill:slug" {
  run bash -c "printf '' | '$BATS_TEST_DIRNAME/../../bin/agent-toolkit' link user claude --plan - skill:alpha --toolkit-repo '$TOOLKIT_ROOT'"
  [ "$status" -eq 2 ]
}

@test "link --all rejects combination with --plan -" {
  run bash -c "printf '' | '$BATS_TEST_DIRNAME/../../bin/agent-toolkit' link user claude --all --plan - --toolkit-repo '$TOOLKIT_ROOT'"
  [ "$status" -eq 2 ]
}

@test "link --plan with no following arg returns rc=2" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --toolkit-repo "$TOOLKIT_ROOT" --plan
  [ "$status" -eq 2 ]
  [[ "$output" == *"--plan"* ]]
}

@test "link --plan with non-dash arg returns rc=2" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --plan myfile.txt --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"--plan"* ]]
}
