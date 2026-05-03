#!/usr/bin/env bats

load 'helpers'

setup() {
  setup_repo
  HOME="$(mktemp -d)"
  export HOME
  mkdir -p "$TOOLKIT_ROOT/skills/alpha"
  cat > "$TOOLKIT_ROOT/skills/alpha/SKILL.md" <<'EOF'
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
  ln -s "$TOOLKIT_ROOT/skills/alpha" "$HOME/.claude/skills/alpha"
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "unlink user claude (bare) errors with hint" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"unlink requires a target"* ]]
  [[ "$output" == *"--all"* ]]
  [[ "$output" == *"<kind>:<slug>"* ]]
  [ -L "$HOME/.claude/skills/alpha" ]   # untouched
}

@test "unlink user claude --all clears symlinks but preserves the YAML file" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude --all --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  [ ! -L "$HOME/.claude/skills/alpha" ]
  [ -f "$HOME/.agent-toolkit.yaml" ]
  grep -q 'alpha' "$HOME/.agent-toolkit.yaml"   # intent preserved
}

@test "unlink user claude skill:alpha removes from file and prunes symlink" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude skill:alpha --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 0 ]
  [ ! -L "$HOME/.claude/skills/alpha" ]
  ! grep -q '^[[:space:]]*-[[:space:]]*alpha' "$HOME/.agent-toolkit.yaml"
}

@test "unlink user claude skill:alpha is idempotent on second run with diagnostic" {
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude skill:alpha --toolkit-repo "$TOOLKIT_ROOT"
  run bash -c "'$BATS_TEST_DIRNAME/../../bin/agent-toolkit' unlink user claude skill:alpha --toolkit-repo '$TOOLKIT_ROOT' 2>&1"
  [ "$status" -eq 0 ]
  [[ "$output" == *"nothing to remove"* ]]
}

@test "unlink user claude skill:alpha when YAML missing errors" {
  rm -f "$HOME/.agent-toolkit.yaml"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude skill:alpha --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"nothing to unlink"* ]]
}

@test "unlink user claude --all leaves unrelated symlinks alone" {
  ln -s /tmp "$HOME/.claude/skills/unrelated"
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude --all --toolkit-repo "$TOOLKIT_ROOT"
  [ -L "$HOME/.claude/skills/unrelated" ]
}

@test "unlink user claude --plan - removes multiple slugs from stdin" {
  # Add a second skill so the batch has >1 entry
  mkdir -p "$TOOLKIT_ROOT/skills/beta"
  cat > "$TOOLKIT_ROOT/skills/beta/SKILL.md" <<'EOF'
---
apiVersion: agent-toolkit/v1alpha1
metadata:
  name: beta
  description: Beta skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - claude
---
EOF
  # Rewrite the YAML to include both, then link both first.
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills:
  - alpha
  - beta
agents: []
commands: []
hooks: []
plugins: []
EOF
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user claude --toolkit-repo "$TOOLKIT_ROOT" >/dev/null 2>&1
  [ -L "$HOME/.claude/skills/alpha" ]
  [ -L "$HOME/.claude/skills/beta" ]

  run bash -c "printf 'skill:alpha\nskill:beta\n' | '$BATS_TEST_DIRNAME/../../bin/agent-toolkit' unlink user claude --plan - --toolkit-repo '$TOOLKIT_ROOT'"
  [ "$status" -eq 0 ]
  [ ! -L "$HOME/.claude/skills/alpha" ]
  [ ! -L "$HOME/.claude/skills/beta" ]
}

@test "unlink --plan - rejects combination with --all" {
  run bash -c "printf '' | '$BATS_TEST_DIRNAME/../../bin/agent-toolkit' unlink user claude --plan - --all --toolkit-repo '$TOOLKIT_ROOT'"
  [ "$status" -eq 2 ]
}

@test "unlink --plan with no following arg returns rc=2" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude --toolkit-repo "$TOOLKIT_ROOT" --plan
  [ "$status" -eq 2 ]
  [[ "$output" == *"--plan"* ]]
}

@test "unlink --plan with non-dash arg returns rc=2" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" unlink user claude --plan myfile.txt --toolkit-repo "$TOOLKIT_ROOT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"--plan"* ]]
}
