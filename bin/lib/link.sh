# shellcheck shell=bash
# Implements `agent-toolkit link <user|project> <harness>`.

. "$(dirname "${BASH_SOURCE[0]}")/_ui.sh"

# Action counters — populated by _maybe_link, read by link_main.
_LINK_CREATED=0
_LINK_UPDATED=0
_LINK_REMOVED=0
_LINK_UNCHANGED=0
_LINK_WOULD_LINK=0
_LINK_WOULD_UNLINK=0

link_main() {
  local scope="$1"; shift
  local harness="$1"; shift
  local repo_root="$PWD"
  local dry_run=0
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo-root) repo_root="$2"; shift 2 ;;
      --dry-run)   dry_run=1; shift ;;
      --quiet|-q)  AGENT_TOOLKIT_QUIET=1; shift ;;
      *) echo "unknown flag: $1" >&2; return 2 ;;
    esac
  done

  # Reset counters (in case link_main is called twice in one process)
  _LINK_CREATED=0
  _LINK_UPDATED=0
  _LINK_REMOVED=0
  _LINK_UNCHANGED=0
  _LINK_WOULD_LINK=0
  _LINK_WOULD_UNLINK=0

  if [ "$dry_run" -eq 1 ]; then
    _ui_header "Previewing $scope-scope changes for $harness (no files will be modified)..."
  else
    case "$scope" in
      user)    _ui_header "Linking user-scope assets for $harness into ~/.$harness/..." ;;
      project) _ui_header "Linking project-scope assets for $harness into ./.$harness/..." ;;
    esac
  fi

  case "$scope" in
    user)    _link_user_scope "$harness" "$repo_root" "$dry_run" ;;
    project) _link_project_scope "$harness" "$repo_root" "$dry_run" ;;
    *) echo "scope must be 'user' or 'project'" >&2; return 2 ;;
  esac

  _link_print_summary "$dry_run"
}

_link_print_summary() {
  local dry_run="$1"
  if [ "$dry_run" -eq 1 ]; then
    local total=$((_LINK_WOULD_LINK + _LINK_WOULD_UNLINK))
    if [ "$total" -eq 0 ]; then
      _ui_summary "Nothing to change."
    else
      _ui_summary "$total changes pending ($_LINK_WOULD_LINK to link, $_LINK_WOULD_UNLINK to remove). Re-run without --dry-run to apply."
    fi
    return
  fi
  local changed=$((_LINK_CREATED + _LINK_UPDATED + _LINK_REMOVED))
  if [ "$changed" -eq 0 ]; then
    _ui_summary "Already in sync — $_LINK_UNCHANGED assets linked, nothing to change."
  else
    _ui_summary "Linked $_LINK_CREATED new, updated $_LINK_UPDATED, removed $_LINK_REMOVED stale ($_LINK_UNCHANGED already in sync)."
  fi
}

_link_user_scope() {
  local harness="$1"
  local repo_root="$2"
  local dry_run="$3"
  local kind
  for kind in skill agent command hook plugin; do
    local target_dir
    target_dir="$(harness_target_dir "$harness" "$kind")"
    [ -n "$target_dir" ] || continue
    [ "$dry_run" -eq 1 ] || mkdir -p "$target_dir"
    while IFS=':' read -r _ slug file; do
      _maybe_link "$harness" "$kind" "$slug" "$file" "$target_dir" "$repo_root" "$dry_run"
    done < <(discover_assets_for_kind "$repo_root" "$kind")
  done
}

_link_project_scope() {
  local harness="$1"
  local repo_root="$2"
  local dry_run="$3"
  local cfg=".agent-toolkit.yaml"
  if [ ! -f "$cfg" ]; then
    echo "no .agent-toolkit.yaml in $PWD — skipping project link" >&2
    return 0
  fi
  local kind
  for kind in skill agent command hook plugin; do
    local target_dir
    target_dir="$(project_target_dir "$harness" "$kind")"
    [ -n "$target_dir" ] || continue
    [ "$dry_run" -eq 1 ] || mkdir -p "$target_dir"
    local section
    case "$kind" in
      skill) section=skills ;; agent) section=agents ;; command) section=commands ;;
      hook)  section=hooks  ;; plugin) section=plugins ;;
    esac
    local allowed
    allowed=$(awk -v sect="$section:" '
      $0 ~ "^"sect { in_sect=1; sub("^"sect, ""); }
      in_sect { print; }
    ' "$cfg" | tr -d '[]," ' | tr '\n' ' ')
    while IFS=':' read -r _ slug file; do
      [[ " $allowed " == *" $slug "* ]] || continue
      _maybe_link "$harness" "$kind" "$slug" "$file" "$target_dir" "$repo_root" "$dry_run"
    done < <(discover_assets_for_kind "$repo_root" "$kind")
  done
}

_maybe_link() {
  local harness="$1"
  local kind="$2"
  local slug="$3"
  local file="$4"
  local target_dir="$5"
  local repo_root="$6"
  local dry_run="$7"

  local source_path
  case "$kind" in
    skill|mcp|plugin) source_path="$(dirname "$file")" ;;
    *) source_path="$file" ;;
  esac
  local link_path="$target_dir/$slug"

  local harnesses
  harnesses=$(read_harnesses_from_frontmatter "$file" || true)
  if ! echo "$harnesses" | grep -qx "$harness"; then
    if [ -L "$link_path" ]; then
      if [ "$dry_run" -eq 1 ]; then
        echo "would-unlink: $link_path"
        _LINK_WOULD_UNLINK=$((_LINK_WOULD_UNLINK + 1))
      else
        rm "$link_path"
        _LINK_REMOVED=$((_LINK_REMOVED + 1))
      fi
    fi
    return
  fi

  if [ -L "$link_path" ] && [ "$(readlink "$link_path")" = "$source_path" ]; then
    _LINK_UNCHANGED=$((_LINK_UNCHANGED + 1))
    return
  fi

  if [ "$dry_run" -eq 1 ]; then
    echo "would-link: $link_path -> $source_path"
    _LINK_WOULD_LINK=$((_LINK_WOULD_LINK + 1))
  else
    if [ -L "$link_path" ] || [ -e "$link_path" ]; then
      _LINK_UPDATED=$((_LINK_UPDATED + 1))
    else
      _LINK_CREATED=$((_LINK_CREATED + 1))
    fi
    rm -f "$link_path"
    ln -s "$source_path" "$link_path"
  fi
}
