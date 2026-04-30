# shellcheck shell=bash

. "$(dirname "${BASH_SOURCE[0]}")/_ui.sh"

list_main() {
  local scope="$1"; shift
  local repo_root="$PWD"
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo-root) repo_root="$2"; shift 2 ;;
      --quiet|-q)  AGENT_TOOLKIT_QUIET=1; shift ;;
      *) echo "unknown flag: $1" >&2; return 2 ;;
    esac
  done

  _ui_header "Symlinks in ${scope}-scope dirs that point into ${repo_root}:"

  local count=0
  local harness kind
  for harness in claude codex opencode pi; do
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
            echo "$harness/$kind/$(basename "$entry") -> $target"
            count=$((count + 1))
            ;;
        esac
      done
    done
  done

  _ui_summary "$count total. Run 'agent-toolkit link $scope <harness> --dry-run' to see drift."
}
