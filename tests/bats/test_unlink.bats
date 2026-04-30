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
  description: Alpha skill.
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

@test "unlink user claude removes symlinks pointing into the repo" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ ! -L "$HOME/.claude/skills/alpha" ]
}

@test "unlink user claude leaves unrelated symlinks untouched" {
  ln -s /tmp "$HOME/.claude/skills/unrelated"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.claude/skills/unrelated" ]
}

@test "unlink user claude emits header and summary on stderr" {
  run bash -c "'$BATS_TEST_DIRNAME/../../bin/agent-toolkit' unlink user claude --repo-root '$REPO_ROOT' 2>&1 >/dev/null"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Removing"* ]]
  [[ "$output" == *"Removed"* ]]
}
