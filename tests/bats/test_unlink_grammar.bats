#!/usr/bin/env bats

load 'helpers'

setup() {
  setup_repo
  HOME="$(mktemp -d)"
  export HOME
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
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills:
  - alpha
agents: []
commands: []
hooks: []
plugins: []
EOF
  mkdir -p "$HOME/.claude/skills"
  ln -s "$REPO_ROOT/skills/alpha" "$HOME/.claude/skills/alpha"
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "unlink user claude (bare) errors with hint" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"unlink requires a target"* ]]
  [[ "$output" == *"--all"* ]]
  [[ "$output" == *"<kind>:<slug>"* ]]
  [ -L "$HOME/.claude/skills/alpha" ]   # untouched
}

@test "unlink user claude --all clears symlinks but preserves the YAML file" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude --all --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ ! -L "$HOME/.claude/skills/alpha" ]
  [ -f "$HOME/.agent-toolkit.yaml" ]
  grep -q 'alpha' "$HOME/.agent-toolkit.yaml"   # intent preserved
}

@test "unlink user claude skill:alpha removes from file and prunes symlink" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude skill:alpha --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ ! -L "$HOME/.claude/skills/alpha" ]
  ! grep -q '^[[:space:]]*-[[:space:]]*alpha' "$HOME/.agent-toolkit.yaml"
}

@test "unlink user claude skill:alpha is idempotent on second run with diagnostic" {
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude skill:alpha --repo-root "$REPO_ROOT"
  run bash -c "'$BATS_TEST_DIRNAME/../../bin/agent-toolkit' unlink user claude skill:alpha --repo-root '$REPO_ROOT' 2>&1"
  [ "$status" -eq 0 ]
  [[ "$output" == *"nothing to remove"* ]]
}

@test "unlink user claude skill:alpha when YAML missing errors" {
  rm -f "$HOME/.agent-toolkit.yaml"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude skill:alpha --repo-root "$REPO_ROOT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"nothing to unlink"* ]]
}

@test "unlink user claude --all leaves unrelated symlinks alone" {
  ln -s /tmp "$HOME/.claude/skills/unrelated"
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude --all --repo-root "$REPO_ROOT"
  [ -L "$HOME/.claude/skills/unrelated" ]
}
