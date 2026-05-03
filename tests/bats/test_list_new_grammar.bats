#!/usr/bin/env bats

load 'helpers'

setup() {
  setup_repo
  HOME="$(mktemp -d)"
  export HOME
  # Three skills:  alpha (claude), beta (claude+codex), gamma (codex only)
  for triple in "alpha:claude" "beta:claude,codex" "gamma:codex"; do
    slug="${triple%%:*}"
    raw_h="${triple##*:}"
    mkdir -p "$TOOLKIT_ROOT/skills/$slug"
    {
      echo '---'
      echo 'apiVersion: agent-toolkit/v1alpha1'
      echo 'metadata:'
      echo "  name: $slug"
      echo "  description: $slug skill."
      echo '  lifecycle: stable'
      echo 'spec:'
      echo '  origin: first-party'
      echo '  vendored_via: none'
      echo '  harnesses:'
      IFS=',' read -ra HS <<< "$raw_h"
      for h in "${HS[@]}"; do
        echo "    - $h"
      done
      echo '---'
    } > "$TOOLKIT_ROOT/skills/$slug/SKILL.md"
  done
  # User scope: alpha installed (in YAML + symlink)
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills:
  - alpha
agents: []
commands: []
hooks: []
plugins: []
EOF
  mkdir -p "$HOME/.claude/skills"
  ln -s "$TOOLKIT_ROOT/skills/alpha" "$HOME/.claude/skills/alpha"
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "list (no args) shows every asset with user/project columns" {
  cd "$TOOLKIT_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha"* ]]
  [[ "$output" == *"beta"* ]]
  [[ "$output" == *"gamma"* ]]
  # alpha is user-installed
  echo "$output" | grep -E '^\s*alpha\b' | grep -q 'user:✓'
  # beta and gamma are not
  echo "$output" | grep -E '^\s*beta\b' | grep -q 'user:—'
  echo "$output" | grep -E '^\s*gamma\b' | grep -q 'user:—'
}

@test "list skill filters to skills only" {
  cd "$TOOLKIT_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list skill --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"SKILLS"* ]]
  # Should not show AGENTS section (none defined here, but header should not appear)
  ! [[ "$output" == *"AGENTS"* ]]
}

@test "list claude filters to claude-compatible assets only" {
  cd "$TOOLKIT_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list claude --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha"* ]]
  [[ "$output" == *"beta"* ]]
  ! [[ "$output" == *"gamma"* ]]
}

@test "list skill claude combines kind and harness filter" {
  cd "$TOOLKIT_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list skill claude --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha"* ]]
  [[ "$output" == *"beta"* ]]
  ! [[ "$output" == *"gamma"* ]]
}

@test "list outside a project shows project:— for all rows" {
  cd "$HOME"   # no .agent-toolkit.yaml in CWD
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"project:—"* ]]
}

@test "list rejects unknown positional argument" {
  cd "$TOOLKIT_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list nonsense --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"nonsense"* ]]
}

@test "list with project YAML present shows project:✓ for installed slug" {
  cat > "$TOOLKIT_ROOT/.agent-toolkit.yaml" <<'EOF'
skills:
  - beta
agents: []
commands: []
hooks: []
plugins: []
EOF
  mkdir -p "$TOOLKIT_ROOT/.claude/skills"
  ln -s "$TOOLKIT_ROOT/skills/beta" "$TOOLKIT_ROOT/.claude/skills/beta"
  cd "$TOOLKIT_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  echo "$output" | grep -E '^\s*beta\b' | grep -q 'project:✓'
}

@test "list mcp emits a clear note instead of empty output" {
  cd "$TOOLKIT_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list mcp --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"mcp"* ]]
  # message goes to stderr — capture combined to assert the note is present
  run bash -c "'$BATS_TEST_DIRNAME/../../bin/agent-toolkit' list mcp --toolkit-repo '$TOOLKIT_ROOT' 2>&1"
  [ "$status" -eq 0 ]
  [[ "$output" == *"not shown here"* ]] || [[ "$output" == *"mcp.json"* ]]
}
