#!/usr/bin/env bash
# audit/build-doc.sh — scaffold/merge docs/audit/<date>-toolkit-audit.md.
#
# Flags:
#   --out PATH         output path (default: docs/audit/YYYY-MM-DD-toolkit-audit.md
#                                            using today's date)
#   --no-empirical     pass-through to discover-matrix.sh

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"

OUT=""
EXTRA_FLAGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --no-empirical) EXTRA_FLAGS+=(--no-empirical); shift ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$OUT" ]; then
  OUT="$REPO_ROOT/docs/audit/$(date +%F)-toolkit-audit.md"
  mkdir -p "$(dirname "$OUT")"
fi

TSV="$(bash "$REPO_ROOT/audit/discover-matrix.sh" "${EXTRA_FLAGS[@]}")"

render_matrix() {
  local src="$1" label="$2"
  printf '### %s\n\n' "$label"
  local kinds harnesses
  kinds=$(printf '%s\n' "$TSV"  | awk -F'\t' -v s="$src" 'NR>1 && $3==s {print $1}' | sort -u)
  harnesses=$(printf '%s\n' "$TSV" | awk -F'\t' -v s="$src" 'NR>1 && $3==s {print $2}' | sort -u)
  # Header row.
  printf '|         |'
  while IFS= read -r h; do [ -n "$h" ] && printf ' %s |' "$h"; done <<< "$harnesses"
  printf '\n|---------|'
  while IFS= read -r h; do [ -n "$h" ] && printf ':---:|'; done <<< "$harnesses"
  printf '\n'
  while IFS= read -r k; do
    [ -z "$k" ] && continue
    printf '| %s |' "$k"
    while IFS= read -r h; do
      [ -z "$h" ] && continue
      local supported
      supported=$(printf '%s\n' "$TSV" | awk -F'\t' -v s="$src" -v k="$k" -v h="$h" \
                  'NR>1 && $3==s && $1==k && $2==h {print $4; exit}')
      case "$supported" in
        true)  printf ' ✓ |' ;;
        false) printf ' — |' ;;
        *)     printf '   |' ;;
      esac
    done <<< "$harnesses"
    printf '\n'
  done <<< "$kinds"
  printf '\n'
}

render_disagreements() {
  printf '### Disagreements\n\n'
  local pairs
  pairs=$(printf '%s\n' "$TSV" | awk -F'\t' 'NR>1 {print $1"\t"$2}' | sort -u)
  local any=0
  while IFS=$'\t' read -r k h; do
    [ -z "$k" ] && continue
    local c s e
    c=$(printf '%s\n' "$TSV" | awk -F'\t' -v k="$k" -v h="$h" '$1==k && $2==h && $3=="code"      {print $4}')
    s=$(printf '%s\n' "$TSV" | awk -F'\t' -v k="$k" -v h="$h" '$1==k && $2==h && $3=="schema"    {print $4}')
    e=$(printf '%s\n' "$TSV" | awk -F'\t' -v k="$k" -v h="$h" '$1==k && $2==h && $3=="empirical" {print $4}')
    if [ -z "$e" ]; then
      [ "$c" != "$s" ] && { printf -- '- %s × %s: code=%s, schema=%s\n' "$k" "$h" "$c" "$s"; any=1; }
    else
      if [ "$c" != "$s" ] || [ "$c" != "$e" ] || [ "$s" != "$e" ]; then
        printf -- '- %s × %s: code=%s, schema=%s, empirical=%s\n' "$k" "$h" "$c" "$s" "$e"
        any=1
      fi
    fi
  done <<< "$pairs"
  if [ "$any" -eq 0 ]; then printf -- '- (none)\n'; fi
  printf '\n'
}

render_cell_stub() {
  local kind="$1" harness="$2"
  cat <<EOF
### ${kind} × ${harness}

<!-- BEGIN_AUDIT:cell ${kind}-${harness} -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — \`audit/demos/${kind}-${harness}.sh\` (\`tmux attach -t audit-${kind}-${harness}\`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell ${kind}-${harness} -->

EOF
}

{
  printf '# Toolkit Audit — %s\n\n' "$(date +%F)"

  printf '## Rollup\n\n'
  printf '<!-- BEGIN_AUDIT:rollup -->\n'
  printf 'Last scaffolded: %s\n\n' "$(date -u +%FT%TZ)"
  printf '_Prioritized issues list — hand-curate below._\n'
  printf '<!-- END_AUDIT:rollup -->\n\n'

  printf '## Support matrix\n\n'
  printf '<!-- BEGIN_AUDIT:matrix -->\n'
  render_matrix code      'Code-derived'
  render_matrix schema    'Schema-derived'
  render_matrix empirical 'Empirical'
  render_disagreements
  printf '<!-- END_AUDIT:matrix -->\n\n'

  printf '## Cells\n\n'
  # Supported = code says true.
  printf '%s\n' "$TSV" | awk -F'\t' '$3=="code" && $4=="true" {print $1"\t"$2}' \
    | sort -u | while IFS=$'\t' read -r k h; do
        render_cell_stub "$k" "$h"
      done
} > "$OUT"

printf 'wrote %s\n' "$OUT"
