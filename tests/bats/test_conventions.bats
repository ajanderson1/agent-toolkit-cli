#!/usr/bin/env bats

load 'helpers'

setup() {
  setup_repo
  HOME="$(mktemp -d)"
  export HOME
  # Conventions tree the repo will link from
  mkdir -p "$REPO_ROOT/conventions"
  cat > "$REPO_ROOT/CONVENTIONS.md" <<'EOF'
# CONVENTIONS (test fixture)
EOF
  cat > "$REPO_ROOT/conventions/git.md" <<'EOF'
# git (test fixture)
EOF
}

teardown() {
  rm -rf "$HOME"
  teardown_repo
}

@test "link user conventions exits 0 (stub)" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
}

@test "link user conventions creates Layer 2 symlinks" {
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.conventions/CONVENTIONS.md" ]
  [ "$(readlink "$HOME/.conventions/CONVENTIONS.md")" = "$REPO_ROOT/CONVENTIONS.md" ]
  [ -L "$HOME/.conventions/conventions" ]
  [ "$(readlink "$HOME/.conventions/conventions")" = "$REPO_ROOT/conventions" ]
}

@test "link user conventions Layer 2 is idempotent" {
  "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  run "$BATS_TEST_DIRNAME/../../bin/agent-toolkit" link user conventions --repo-root "$REPO_ROOT"
  [ "$status" -eq 0 ]
  [ -L "$HOME/.conventions/CONVENTIONS.md" ]
  [ "$(readlink "$HOME/.conventions/CONVENTIONS.md")" = "$REPO_ROOT/CONVENTIONS.md" ]
}
