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
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "link user claude --all creates file with every compatible slug" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --all --yes --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  [ -f "$HOME/.agent-toolkit.yaml" ]
  grep -q 'alpha' "$HOME/.agent-toolkit.yaml"
  grep -q 'beta' "$HOME/.agent-toolkit.yaml"
  [ -L "$HOME/.claude/skills/alpha" ]
  [ -L "$HOME/.claude/skills/beta" ]
}

@test "link user claude --all overwrites existing populated file with -y" {
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills:
  - oldslug
agents: []
commands: []
hooks: []
plugins: []
EOF
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --all -y --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  ! grep -q 'oldslug' "$HOME/.agent-toolkit.yaml"
  grep -q 'alpha' "$HOME/.agent-toolkit.yaml"
}

@test "link user claude --all in non-TTY without -y refuses" {
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills:
  - oldslug
agents: []
commands: []
hooks: []
plugins: []
EOF
  run bash -c "'$BATS_TEST_DIRNAME/../../bin/agent-toolkit' link user claude --all --toolkit-repo '$TOOLKIT_ROOT' </dev/null"
  [ "$status" -ne 0 ]
  [[ "$output" == *"no TTY"* ]]
  grep -q 'oldslug' "$HOME/.agent-toolkit.yaml"
}

@test "link user claude --all on empty existing file does not prompt" {
  printf '' > "$HOME/.agent-toolkit.yaml"
  run bash -c "'$BATS_TEST_DIRNAME/../../bin/agent-toolkit' link user claude --all --toolkit-repo '$TOOLKIT_ROOT' </dev/null"
  [ "$status" -eq 0 ]
  grep -q 'alpha' "$HOME/.agent-toolkit.yaml"
}

@test "link user claude --all --dry-run reports would-be slugs (not old file)" {
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills:
  - oldslug
agents: []
commands: []
hooks: []
plugins: []
EOF
  run bash -c "'$BATS_TEST_DIRNAME/../../bin/agent-toolkit' link user claude --all -y --dry-run --toolkit-repo '$TOOLKIT_ROOT' 2>&1"
  [ "$status" -eq 0 ]
  # Should mention the actual repo slugs (alpha, beta), not oldslug
  [[ "$output" == *"alpha"* ]] || [[ "$output" == *"pending"* ]]
  # The user's actual file should NOT have been written
  grep -q 'oldslug' "$HOME/.agent-toolkit.yaml"
  ! grep -q 'alpha' "$HOME/.agent-toolkit.yaml"
}
