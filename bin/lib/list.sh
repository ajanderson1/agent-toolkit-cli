# shellcheck shell=bash
# Implements `agent-toolkit list [<kind>] [<harness>]`.

. "$(dirname "${BASH_SOURCE[0]}")/_ui.sh"
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

_KNOWN_KINDS="skill agent command hook plugin mcp"
_KNOWN_HARNESSES="claude codex opencode pi"

_is_known_kind() { case " $_KNOWN_KINDS " in *" $1 "*) return 0 ;; esac; return 1; }
_is_known_harness() { case " $_KNOWN_HARNESSES " in *" $1 "*) return 0 ;; esac; return 1; }

list_main() {
  local repo_root="$PWD"
  local kind_filter="" harness_filter="" format="text"
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo-root) repo_root="$2"; shift 2 ;;
      --quiet|-q)  AGENT_TOOLKIT_QUIET=1; shift ;;
      --format)    format="$2"; shift 2 ;;
      --format=*)  format="${1#--format=}"; shift ;;
      -*) echo "unknown flag: $1" >&2; return 2 ;;
      *)
        if _is_known_kind "$1"; then
          [ -z "$kind_filter" ] || { echo "duplicate kind filter: $1" >&2; return 2; }
          kind_filter="$1"
        elif _is_known_harness "$1"; then
          [ -z "$harness_filter" ] || { echo "duplicate harness filter: $1" >&2; return 2; }
          harness_filter="$1"
        else
          echo "unknown filter '$1' — expected one of: $_KNOWN_KINDS or $_KNOWN_HARNESSES" >&2
          return 2
        fi
        shift
        ;;
    esac
  done

  case "$format" in
    text|json) ;;
    *) echo "unknown --format: $format (expected: text, json)" >&2; return 2 ;;
  esac

  if [ "$format" = "json" ]; then
    local _at_project
    _at_project="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    exec uv run --project "$_at_project" \
      agent-toolkit _list-json --repo-root "$repo_root" \
      ${kind_filter:+--kind "$kind_filter"} \
      ${harness_filter:+--harness "$harness_filter"}
  fi

  if [ "$kind_filter" = "mcp" ]; then
    _ui_header "Asset inventory (filter: kind=mcp):"
    _ui_summary "MCPs are configured via the harness's mcp.json, not symlinks — not shown here."
    return 0
  fi

  _ui_header "Asset inventory (filter: kind=${kind_filter:-any}, harness=${harness_filter:-any}):"

  local user_yaml="$HOME/.agent-toolkit.yaml"
  local project_yaml="$PWD/.agent-toolkit.yaml"

  local kind
  for kind in skill agent command hook plugin; do
    [ -z "$kind_filter" ] || [ "$kind_filter" = "$kind" ] || continue

    # Collect rows for this kind
    local rows=""
    local count=0
    while IFS=':' read -r _ slug file; do
      local harnesses
      harnesses=$(read_harnesses_from_frontmatter "$file" || true)
      if [ -n "$harness_filter" ]; then
        echo "$harnesses" | grep -qx "$harness_filter" || continue
      fi
      local user_state project_state
      user_state="$(_list_install_state "$user_yaml" "$kind" "$slug" "$harnesses" "$harness_filter" user)"
      project_state="$(_list_install_state "$project_yaml" "$kind" "$slug" "$harnesses" "$harness_filter" project)"
      local h_display=""
      if [ -z "$harness_filter" ]; then
        h_display="[$(echo "$harnesses" | tr '\n' ' ' | sed 's/[[:space:]]*$//')]"
      fi
      printf -v row '  %-20s %-30s user:%s project:%s\n' "$slug" "$h_display" "$user_state" "$project_state"
      rows+="$row"
      count=$((count + 1))
    done < <(discover_assets_for_kind "$repo_root" "$kind")

    if [ -n "$rows" ]; then
      local section_title
      case "$kind" in
        skill)   section_title="SKILLS" ;;
        agent)   section_title="AGENTS" ;;
        command) section_title="COMMANDS" ;;
        hook)    section_title="HOOKS" ;;
        plugin)  section_title="PLUGINS" ;;
      esac
      echo "$section_title ($count)"
      printf '%s' "$rows"
    fi
  done

  _ui_summary "Done."
}

# Determine the install state ✓/— for one asset against one allow-list YAML.
# Args: yaml_path kind slug asset_harnesses harness_filter scope
# A symlink-existence check is included for user scope; project scope checks
# against $PWD/.<harness>/<kind>/<slug>.
_list_install_state() {
  local yaml="$1" kind="$2" slug="$3" asset_harnesses="$4" harness_filter="$5" scope="$6"
  [ -f "$yaml" ] || { echo "—"; return; }
  local section
  section="$(kind_to_section "$kind")" 2>/dev/null || { echo "—"; return; }
  local listed=0
  while IFS= read -r s; do
    if [ "$s" = "$slug" ]; then listed=1; break; fi
  done < <(read_allowlist_section "$yaml" "$section")
  [ "$listed" -eq 1 ] || { echo "—"; return; }

  # If a harness filter is set, only check that harness; else check whether ANY
  # declared harness has a symlink.
  local harnesses_to_check
  if [ -n "$harness_filter" ]; then
    harnesses_to_check="$harness_filter"
  else
    harnesses_to_check="$asset_harnesses"
  fi
  local h
  while IFS= read -r h; do
    [ -n "$h" ] || continue
    local target_dir
    if [ "$scope" = "user" ]; then
      target_dir="$(harness_target_dir "$h" "$kind")"
    else
      target_dir="$(project_target_dir "$h" "$kind")"
    fi
    [ -n "$target_dir" ] || continue
    if [ -L "$target_dir/$slug" ]; then echo "✓"; return; fi
  done <<< "$harnesses_to_check"
  echo "—"
}
