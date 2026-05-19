#!/usr/bin/env bash
# audit/discover-matrix.sh — emit the support matrix as 4-col TSV.
#
# Output:  kind \t harness \t source \t supported
# Sources: code | schema | empirical
#
# Flags:
#   --no-empirical   skip the empirical probe (faster, used in tests).
#
# MCP empirical note: linking an MCP edits a config file (e.g. .mcp.json)
# rather than creating a named symlink. The heuristic therefore falls back
# to a content-grep under probe_dir when the filename search finds nothing,
# so MCPs are not silently reported as false-negatives.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"

DO_EMPIRICAL=1
for arg in "$@"; do
  case "$arg" in
    --no-empirical) DO_EMPIRICAL=0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

SCHEMA="$REPO_ROOT/src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json"

printf 'kind\tharness\tsource\tsupported\n'

# --- code ---
uv run --project "$REPO_ROOT" python "$REPO_ROOT/audit/lib/code_probe.py" \
  | awk -F'\t' 'NR>1 { printf "%s\t%s\tcode\t%s\n", $1, $2, $3 }'

# --- schema ---
# Read kinds from metadata.kind enum (direct path).
KINDS=$(jq -r '.properties.metadata.properties.kind.enum[]' "$SCHEMA" 2>/dev/null | sort -u)
# Read harnesses from spec.harnesses.items enum (direct path).
HARNESSES=$(jq -r '.properties.spec.properties.harnesses.items.enum[]' "$SCHEMA" 2>/dev/null | sort -u)

# Fall back to known sets if jq returns nothing (schema shape may evolve).
if [ -z "$KINDS" ]; then
  KINDS=$'agent\ncommand\nhook\nmcp\npi-extension\nplugin\nskill'
fi
if [ -z "$HARNESSES" ]; then
  HARNESSES=$'claude\ncodex\ngemini\nopencode\npi'
fi

while IFS= read -r k; do
  [ -z "$k" ] && continue
  while IFS= read -r h; do
    [ -z "$h" ] && continue
    printf '%s\t%s\tschema\ttrue\n' "$k" "$h"
  done <<< "$HARNESSES"
done <<< "$KINDS"

# --- empirical ---
if [ "$DO_EMPIRICAL" -eq 0 ]; then
  exit 0
fi

source "$REPO_ROOT/audit/lib/sandbox.sh"

# For each (kind, harness) the code probe claims supported, attempt a link
# in a fresh sandbox and check whether the asset materialised under the
# harness's projection root — either as a named file/symlink, or (for MCPs
# that write into config files) as a string within those files.
uv run --project "$REPO_ROOT" python "$REPO_ROOT/audit/lib/code_probe.py" \
  | awk -F'\t' 'NR>1 && $3=="true" { print $1"\t"$2 }' \
  | while IFS=$'\t' read -r kind harness; do
      (
        sandbox::init
        slug="demo-${kind}"
        if agent-toolkit-cli link user "$harness" "${kind}:${slug}" >/dev/null 2>&1; then
          case "$harness" in
            claude)   probe_dir="$CLAUDE_CONFIG_DIR" ;;
            codex)    probe_dir="$CODEX_HOME" ;;
            *)        probe_dir="$HOME" ;;
          esac
          # Named-file check (symlinks, directories, plain files).
          named_found=0
          if find "$probe_dir" -name "*${slug}*" -print -quit 2>/dev/null | grep -q .; then
            named_found=1
          fi
          # Content-grep fallback: catches MCPs that write the slug into a
          # JSON/TOML config file rather than as a filesystem entry name.
          # Claude's MCP config lands at $HOME/.claude.json (sibling of
          # $CLAUDE_CONFIG_DIR, not inside it), so we search $HOME broadly.
          content_found=0
          if grep -rqF "${slug}" "$HOME" 2>/dev/null; then
            content_found=1
          fi
          if [ "$named_found" -eq 1 ] || [ "$content_found" -eq 1 ]; then
            printf '%s\t%s\tempirical\ttrue\n' "$kind" "$harness"
          else
            printf '%s\t%s\tempirical\tfalse\n' "$kind" "$harness"
          fi
        else
          printf '%s\t%s\tempirical\tfalse\n' "$kind" "$harness"
        fi
      )
    done
