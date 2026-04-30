# shellcheck shell=bash
# Implements `agent-toolkit link <user|project> <harness>`.

link_main() {
  local scope="$1"; shift
  local harness="$1"; shift
  local repo_root="$PWD"
  local dry_run=0
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo-root) repo_root="$2"; shift 2 ;;
      --dry-run)   dry_run=1; shift ;;
      *) echo "unknown flag: $1" >&2; return 2 ;;
    esac
  done
  case "$scope" in
    user)    _link_user_scope "$harness" "$repo_root" "$dry_run" ;;
    project) _link_project_scope "$harness" "$repo_root" "$dry_run" ;;
    *) echo "scope must be 'user' or 'project'" >&2; return 2 ;;
  esac
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
    # Read the section's slug list
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

  # Read harness compatibility
  local harnesses
  harnesses=$(read_harnesses_from_frontmatter "$file" || true)
  if ! echo "$harnesses" | grep -qx "$harness"; then
    # Asset doesn't support this harness — remove stale link if present.
    if [ -L "$link_path" ]; then
      [ "$dry_run" -eq 1 ] && echo "would-unlink: $link_path" || rm "$link_path"
    fi
    return
  fi
  if [ -L "$link_path" ] && [ "$(readlink "$link_path")" = "$source_path" ]; then
    return  # already correct
  fi
  if [ "$dry_run" -eq 1 ]; then
    echo "would-link: $link_path -> $source_path"
  else
    rm -f "$link_path"
    ln -s "$source_path" "$link_path"
  fi
}
