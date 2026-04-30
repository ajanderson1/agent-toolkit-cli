# shellcheck shell=bash

# Set REPO_ROOT to a fresh tempdir, copy schema + minimal layout into it.
setup_repo() {
  REPO_ROOT="$(mktemp -d)"
  export REPO_ROOT
  mkdir -p "$REPO_ROOT/schemas"
  cp "$BATS_TEST_DIRNAME/../../schemas/asset-frontmatter.v1alpha1.json" \
     "$REPO_ROOT/schemas/asset-frontmatter.v1alpha1.json"
}

teardown_repo() {
  rm -rf "$REPO_ROOT"
  unset REPO_ROOT
}
