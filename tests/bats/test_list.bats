#!/usr/bin/env bats

load 'helpers'

setup() {
  setup_repo
  HOME="$(mktemp -d)"
  export HOME
  mkdir -p "$HOME/.claude/skills"
  mkdir -p "$REPO_ROOT/skills/alpha"
  cat > "$REPO_ROOT/skills/alpha/SKILL.md" <<'EOF'
---
apiVersion: agent-toolkit/v1alpha1
metadata:
  name: alpha
  description: Alpha.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - claude
---
EOF
  ln -s "$REPO_ROOT/skills/alpha" "$HOME/.claude/skills/alpha"
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "list shows alpha as user:✓ when user YAML lists it and symlink exists" {
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills:
  - alpha
agents: []
commands: []
hooks: []
plugins: []
EOF
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha"* ]]
  [[ "$output" == *"user:✓"* ]]
}

@test "list emits a header and summary on stderr" {
  run bash -c "'$BATS_TEST_DIRNAME/../../bin/agent-toolkit' list --repo-root '$REPO_ROOT' 2>&1 >/dev/null"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Asset inventory"* ]]
  [[ "$output" == *"Done"* ]]
}

@test "list is quiet under AGENT_TOOLKIT_QUIET=1" {
  run bash -c "AGENT_TOOLKIT_QUIET=1 '$BATS_TEST_DIRNAME/../../bin/agent-toolkit' list --repo-root '$REPO_ROOT' 2>&1 >/dev/null"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
