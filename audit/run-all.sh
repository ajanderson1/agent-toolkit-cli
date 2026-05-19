#!/usr/bin/env bash
# audit/run-all.sh — run every demo headlessly, record exit codes to TSV.
set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"

OUT="$REPO_ROOT/audit/.last-run.tsv"
printf 'cell\texit_code\tts\n' > "$OUT"

for demo in "$REPO_ROOT"/audit/demos/*.sh; do
  [ -f "$demo" ] || continue
  cell="$(basename "$demo" .sh)"
  rc=0
  PAUSE_SCALE=0 AUDIT_INSIDE_TMUX=1 bash "$demo" < /dev/null > "$REPO_ROOT/audit/.${cell}.log" 2>&1 || rc=$?
  printf '%s\t%d\t%s\n' "$cell" "$rc" "$(date -u +%FT%TZ)" >> "$OUT"
  printf '  %s\t%s\n' "$cell" "$([ "$rc" -eq 0 ] && echo PASS || echo "FAIL($rc)")"
done

printf '\nresults: %s\n' "$OUT"
