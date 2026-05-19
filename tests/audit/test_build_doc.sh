#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib.sh"

TMPDOC="$(mktemp)"
bash "$REPO_ROOT/audit/build-doc.sh" --out "$TMPDOC" --no-empirical

t::run "produces a Toolkit Audit document" '
  t::assert "title present"    "grep -q \"# Toolkit Audit\" \"$TMPDOC\""
  t::assert "rollup section"   "grep -q \"## Rollup\" \"$TMPDOC\""
  t::assert "matrix section"   "grep -q \"## Support matrix\" \"$TMPDOC\""
  t::assert "cells section"    "grep -q \"## Cells\" \"$TMPDOC\""
'

t::run "embeds a code-derived matrix table" '
  t::assert "Code-derived heading" "grep -q \"### Code-derived\" \"$TMPDOC\""
'

t::run "creates cell stubs for supported cells" '
  t::assert "skill x claude stub"   "grep -q \"### skill × claude\" \"$TMPDOC\""
  t::assert "skill x claude marker" "grep -q \"BEGIN_AUDIT:cell skill-claude\" \"$TMPDOC\""
'

rm -f "$TMPDOC"
t::summary
