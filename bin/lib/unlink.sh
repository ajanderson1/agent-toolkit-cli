# shellcheck shell=bash
# Implements `agent-toolkit unlink <user|project> <harness> [...]`.

. "$(dirname "${BASH_SOURCE[0]}")/_ui.sh"
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"
. "$(dirname "${BASH_SOURCE[0]}")/link.sh"   # for _link_project_from_file (re-projection on per-asset)

_unlink_allowlist_path() {
  case "$1" in
    user)    echo "$HOME/.agent-toolkit.yaml" ;;
    project) echo "$PWD/.agent-toolkit.yaml" ;;
    *)       echo ""; return 1 ;;
  esac
}

unlink_main() {
  local scope="$1"; shift
  local harness="$1"; shift
  local repo_root="$PWD"
  local dry_run=0
  local mode="bare"
  local kind="" slug=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo-root) repo_root="$2"; shift 2 ;;
      --dry-run)   dry_run=1; shift ;;
      --quiet|-q)  AGENT_TOOLKIT_QUIET=1; shift ;;
      --all)
        if [ "$mode" != "bare" ]; then
          echo "cannot combine --all with $mode mode" >&2; return 2
        fi
        mode="all"
        shift
        ;;
      --plan)
        if [ "$mode" != "bare" ]; then
          echo "cannot combine --plan with $mode mode" >&2; return 2
        fi
        if [ "$#" -lt 2 ] || [ "${2:-}" != "-" ]; then
          echo "--plan currently supports only '-' (stdin)" >&2; return 2
        fi
        mode="plan"
        shift 2
        ;;
      *:*)
        if [ "$mode" != "bare" ]; then
          echo "cannot combine ${1} with $mode mode" >&2; return 2
        fi
        mode="per-asset"
        kind="${1%%:*}"
        slug="${1#*:}"
        shift
        ;;
      *) echo "unknown flag: $1" >&2; return 2 ;;
    esac
  done

  case "$scope" in user|project) ;; *) echo "scope must be 'user' or 'project'" >&2; return 2 ;; esac

  local allowlist_path
  allowlist_path="$(_unlink_allowlist_path "$scope")"

  case "$mode" in
    bare)      _unlink_bare_error "$scope" "$harness" "$allowlist_path" ;;
    all)       _unlink_all "$scope" "$harness" "$repo_root" "$dry_run" ;;
    per-asset) _unlink_per_asset "$scope" "$harness" "$kind" "$slug" "$repo_root" "$allowlist_path" "$dry_run" ;;
    plan)      _unlink_plan "$scope" "$harness" "$repo_root" "$allowlist_path" "$dry_run" ;;
  esac
}

_unlink_bare_error() {
  local scope="$1" harness="$2" allowlist_path="$3"
  cat >&2 <<EOF
unlink requires a target. Did you mean:
  agent-toolkit unlink $scope $harness --all                  → remove all symlinks for $harness (preserves $allowlist_path)
  agent-toolkit unlink $scope $harness <kind>:<slug>          → remove one asset (also removes from $allowlist_path)
Run 'agent-toolkit list $harness' to see what's currently linked.
EOF
  return 2
}

_unlink_all() {
  local scope="$1" harness="$2" repo_root="$3" dry_run="$4"

  if [ "$dry_run" -eq 1 ]; then
    _ui_header "Previewing removal of $scope-scope $harness symlinks pointing into $repo_root..."
  else
    _ui_header "Removing $scope-scope $harness symlinks pointing into $repo_root..."
  fi

  local removed=0
  local kind
  for kind in skill agent command hook plugin; do
    local target_dir
    if [ "$scope" = "user" ]; then
      target_dir="$(harness_target_dir "$harness" "$kind")"
    else
      target_dir="$(project_target_dir "$harness" "$kind")"
    fi
    [ -n "$target_dir" ] || continue
    [ -d "$target_dir" ] || continue
    local entry
    for entry in "$target_dir"/*; do
      [ -L "$entry" ] || continue
      local target
      target="$(readlink "$entry")"
      case "$target" in
        "$repo_root"/*)
          if [ "$dry_run" -eq 1 ]; then
            echo "would-unlink: $entry"
          else
            rm "$entry"
          fi
          removed=$((removed + 1))
          ;;
      esac
    done
  done

  if [ "$dry_run" -eq 1 ]; then
    _ui_summary "$removed symlinks would be removed."
  else
    _ui_summary "Removed $removed symlinks."
  fi
}

_unlink_per_asset() {
  local scope="$1" harness="$2" kind="$3" slug="$4"
  local repo_root="$5" allowlist_path="$6" dry_run="$7"

  if [ "$kind" = "mcp" ]; then
    echo "mcps are not yet scope-routed — edit the harness's mcp.json directly" >&2
    return 2
  fi

  local section
  section="$(kind_to_section "$kind")" || return 2

  if [ ! -f "$allowlist_path" ]; then
    echo "no $allowlist_path — nothing to unlink." >&2
    return 1
  fi

  # Idempotent diagnostic: if the slug is already absent, say so and exit zero.
  local already_listed=0
  while IFS= read -r s; do
    if [ "$s" = "$slug" ]; then already_listed=1; break; fi
  done < <(read_allowlist_section "$allowlist_path" "$section")
  if [ "$already_listed" -eq 0 ]; then
    echo "$kind:$slug not in $allowlist_path — nothing to remove." >&2
    return 0
  fi

  if [ "$dry_run" -eq 0 ]; then
    uv run --project "$_AT_TOOLKIT_PROJECT" agent-toolkit _yaml-edit remove "$allowlist_path" "$section" "$slug" || return 1
  fi

  _ui_header "Unlinking $scope-scope $kind:$slug for $harness..."

  # Reset link counters and re-project to prune
  _LINK_CREATED=0; _LINK_UPDATED=0; _LINK_REMOVED=0
  _LINK_UNCHANGED=0; _LINK_WOULD_LINK=0; _LINK_WOULD_UNLINK=0
  _link_project_from_file "$scope" "$harness" "$repo_root" "$allowlist_path" "$dry_run"
  _link_print_summary "$dry_run"
}

# === --plan - form ==========================================================
# Reads `<kind>:<slug>` entries from stdin (one per line), ignores `#`-comments
# and blank lines, applies each entry independently via _unlink_per_asset.
# Per-entry failures are reported on stderr but do NOT abort the batch.
# Returns 0 if every entry succeeded; 1 if any entry failed.
_unlink_plan() {
  local scope="$1" harness="$2" repo_root="$3" allowlist_path="$4" dry_run="$5"
  local ok=0 failed=0 total=0
  local errors=""

  local plan_file plan_err
  plan_file="$(mktemp -t agent-toolkit-plan.XXXXXX)"
  plan_err="${plan_file}.err"
  # Ensure tempfiles are removed on SIGINT/SIGTERM even if the function is
  # interrupted mid-loop. The explicit rm at the end still runs on normal exit.
  trap 'rm -f "$plan_file" "$plan_err"; exit 130' INT TERM
  cat - > "$plan_file"

  while IFS= read -r raw; do
    local line="${raw%%#*}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [ -n "$line" ] || continue
    case "$line" in
      *:*) ;;
      *) errors+="malformed (no kind:slug): $raw"$'\n'; failed=$((failed+1)); total=$((total+1)); continue ;;
    esac
    total=$((total+1))
    if AGENT_TOOLKIT_QUIET=1 _unlink_per_asset "$scope" "$harness" "${line%%:*}" "${line#*:}" \
         "$repo_root" "$allowlist_path" "$dry_run" >/dev/null 2>>"$plan_err"; then
      ok=$((ok+1))
    else
      failed=$((failed+1))
      errors+="failed: $line"$'\n'
    fi
  done < "$plan_file"

  if [ -n "$errors" ]; then
    printf '%s' "$errors" >&2
  fi
  if [ -s "$plan_err" ]; then
    cat "$plan_err" >&2
  fi
  rm -f "$plan_file" "$plan_err"
  trap - INT TERM

  _ui_summary "Plan applied: $ok ok, $failed failed (of $total entries)."
  if [ "$failed" -gt 0 ]; then return 1; fi
  return 0
}
