# shellcheck shell=bash

list_main() {
  local scope="$1"; shift
  local repo_root="$PWD"
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo-root) repo_root="$2"; shift 2 ;;
      *) echo "unknown flag: $1" >&2; return 2 ;;
    esac
  done
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
            ;;
        esac
      done
    done
  done
}
