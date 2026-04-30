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
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "diff user claude shows what link would create" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" diff user claude --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"would-link"* ]]
}

@test "diff user claude emits a 'Previewing' header on stderr" {
  run bash -c "'$BATS_TEST_DIRNAME/../../bin/agent-toolkit' diff user claude --repo-root '$REPO_ROOT' 2>&1 >/dev/null"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Previewing"* ]]
}
