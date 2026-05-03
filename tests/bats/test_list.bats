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

@test "list --format=json emits valid JSON with assets and cells" {
  cat > "$HOME/.agent-toolkit.yaml" <<'EOF'
skills:
  - alpha
agents: []
commands: []
hooks: []
plugins: []
EOF
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list --format=json --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  echo "$output" | uv run python -c "import json,sys; d=json.load(sys.stdin); assert d['repo_root']=='$REPO_ROOT'; assert any(a['slug']=='alpha' for a in d['assets']); cells=[c for a in d['assets'] if a['slug']=='alpha' for c in a['cells']]; assert any(c['harness']=='claude' and c['scope']=='user' and c['status']=='linked' for c in cells), cells"
}

@test "list --format=json marks unsupported cells correctly" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" list --format=json --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  echo "$output" | uv run python -c "import json,sys; d=json.load(sys.stdin); cells=[c for a in d['assets'] if a['slug']=='alpha' for c in a['cells']]; assert any(c['harness']=='codex' and c['status']=='unsupported' for c in cells), cells"
}
