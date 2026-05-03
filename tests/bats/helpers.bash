# shellcheck shell=bash

# Set TOOLKIT_ROOT to a fresh tempdir, copy schema + minimal layout into it.
# The fixture serves as both the SSOT toolkit repo and (for project-scope
# tests that cd into it) the consumer project.
setup_repo() {
  TOOLKIT_ROOT="$(mktemp -d)"
  export TOOLKIT_ROOT
  mkdir -p "$TOOLKIT_ROOT/schemas"
  cp "$BATS_TEST_DIRNAME/../../schemas/asset-frontmatter.v1alpha1.json" \
     "$TOOLKIT_ROOT/schemas/asset-frontmatter.v1alpha1.json"
  echo 'tool: agent-toolkit-cli' > "$TOOLKIT_ROOT/.agent-toolkit-source"
}

teardown_repo() {
  rm -rf "$TOOLKIT_ROOT"
  unset TOOLKIT_ROOT
}
