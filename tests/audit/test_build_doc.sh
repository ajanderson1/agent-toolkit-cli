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

t::run "second run preserves hand-edited cell prose" '
  local doc; doc="$(mktemp)"
  bash "$REPO_ROOT/audit/build-doc.sh" --out "$doc" --no-empirical
  # Inject hand-edited content into the skill-claude cell.
  perl -i -pe "s|_hand-fill_|MY HAND-WRITTEN PROSE| if /BEGIN_AUDIT:cell skill-claude/ ... /END_AUDIT:cell skill-claude/" "$doc"
  grep -q "MY HAND-WRITTEN PROSE" "$doc" || { echo "setup failed: hand-edit not present" >&2; return 1; }
  bash "$REPO_ROOT/audit/build-doc.sh" --out "$doc" --no-empirical
  t::assert "hand-written prose preserved" "grep -q \"MY HAND-WRITTEN PROSE\" \"$doc\""
  rm -f "$doc"
'

t::run "second run preserves the rollup hand-curated list" '
  local doc; doc="$(mktemp)"
  bash "$REPO_ROOT/audit/build-doc.sh" --out "$doc" --no-empirical
  perl -i -pe "s|_Prioritized issues list — hand-curate below._|- ISSUE-1: MY ROLLUP NOTE|" "$doc"
  bash "$REPO_ROOT/audit/build-doc.sh" --out "$doc" --no-empirical
  t::assert "rollup note preserved" "grep -q \"MY ROLLUP NOTE\" \"$doc\""
  rm -f "$doc"
'

t::summary
