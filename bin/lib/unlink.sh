# shellcheck shell=bash

. "$(dirname "${BASH_SOURCE[0]}")/_ui.sh"

unlink_main() {
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
