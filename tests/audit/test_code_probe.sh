#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib.sh"

OUT="$(uv run --project "$REPO_ROOT" python "$REPO_ROOT/audit/lib/code_probe.py")"

t::run "emits a header line" '
  t::assert "header present" "[[ \"$OUT\" == kind*harness* ]]"
'

t::run "claims skill x claude is supported" '
  if ! printf "%s\n" "$OUT" | awk -F"\t" "\$1==\"skill\" && \$2==\"claude\" && \$3==\"true\" {found=1} END {exit !found}"; then
    echo "expected skill x claude to be supported" >&2; return 1
  fi
'

t::run "claims agent x codex is NOT supported (no slot)" '
  if printf "%s\n" "$OUT" | awk -F"\t" "\$1==\"agent\" && \$2==\"codex\" && \$3==\"true\" {found=1} END {exit !found}"; then
    echo "agent x codex should not be supported" >&2; return 1
  fi
'

t::summary
