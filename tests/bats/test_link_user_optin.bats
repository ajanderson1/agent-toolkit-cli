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
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "link user claude with no ~/.agent-toolkit.yaml errors with hint" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no $HOME/.agent-toolkit.yaml"* ]]
  [[ "$output" == *"--all"* ]]
  [[ "$output" == *"<kind>:<slug>"* ]]
  [ ! -L "$HOME/.claude/skills/alpha" ]
}

@test "link user claude with empty ~/.agent-toolkit.yaml succeeds and links nothing" {
  printf '' > "$HOME/.agent-toolkit.yaml"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ ! -L "$HOME/.claude/skills/alpha" ]
}

@test "link user claude with allow-listed slug links it" {
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills:
  - alpha
agents: []
commands: []
hooks: []
plugins: []
EOF
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.claude/skills/alpha" ]
}

@test "link user claude does NOT link slug missing from allow-list" {
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills: []
agents: []
commands: []
hooks: []
plugins: []
EOF
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ ! -L "$HOME/.claude/skills/alpha" ]
}

@test "link user claude prunes symlink when slug is removed from allow-list" {
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills:
  - alpha
agents: []
commands: []
hooks: []
plugins: []
EOF
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  [ -L "$HOME/.claude/skills/alpha" ]
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills: []
agents: []
commands: []
hooks: []
plugins: []
EOF
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ ! -L "$HOME/.claude/skills/alpha" ]
}

@test "link user claude prunes orphan symlink for asset removed from repo" {
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills:
  - alpha
agents: []
commands: []
hooks: []
plugins: []
EOF
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  [ -L "$HOME/.claude/skills/alpha" ]
  # Simulate orphan: another claude-compatible skill that gets removed from the repo
  mkdir -p "$REPO_ROOT/skills/orphan"
  cat > "$REPO_ROOT/skills/orphan/SKILL.md" <<'EOF'
---
apiVersion: agent-toolkit/v1alpha1
metadata:
  name: orphan
  description: Orphan skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - claude
---
EOF
  ln -s "$REPO_ROOT/skills/orphan" "$HOME/.claude/skills/orphan"
  rm -rf "$REPO_ROOT/skills/orphan"
  [ -L "$HOME/.claude/skills/orphan" ]   # symlink remains
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ ! -L "$HOME/.claude/skills/orphan" ]   # orphan pruned
  [ -L "$HOME/.claude/skills/alpha" ]      # alpha still there
}
