#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib.sh"

OUT="$(bash "$REPO_ROOT/audit/discover-matrix.sh" --no-empirical)"

t::run "emits header" '
  t::assert "header" "[[ \"$OUT\" == kind*harness*source*supported* ]]"
'

t::run "covers code and schema sources" '
  t::assert "has code rows"   "[[ \"$OUT\" == *code* ]]"
  t::assert "has schema rows" "[[ \"$OUT\" == *schema* ]]"
'

t::summary
