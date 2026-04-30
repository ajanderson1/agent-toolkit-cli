# shellcheck shell=bash
# Implements the conventions-projection subcommands:
#   agent-toolkit link/unlink/list/diff user conventions
#
# Layer 1 (source of truth): the conventions tree inside this repo.
# Layer 2 (neutral pointer):  ~/.conventions/CONVENTIONS.md (file symlink)
#                             ~/.conventions/conventions/   (dir symlink)
# Layer 3 (per-harness slot): symlinks pointing at Layer 2.
#
# See docs/superpowers/specs/2026-04-30-neutral-conventions-path-design.md.

# Per-harness Layer 3 mapping. Empty target dir means "harness not detected".
# Echoes "$slot_path|$layer2_target" pairs, one per line, for each harness whose
# config dir exists.
_conventions_layer3_slots() {
  if [ -d "$HOME/.claude" ]; then
    echo "$HOME/.claude/CONVENTIONS.md|$HOME/.conventions/CONVENTIONS.md"
    echo "$HOME/.claude/conventions|$HOME/.conventions/conventions"
  fi
  if [ -d "$HOME/.codex" ]; then
    echo "$HOME/.codex/AGENTS.md|$HOME/.conventions/CONVENTIONS.md"
  fi
  if [ -d "$HOME/.config/opencode" ]; then
    echo "$HOME/.config/opencode/AGENTS.md|$HOME/.conventions/CONVENTIONS.md"
  fi
  if [ -d "$HOME/.pi/agent" ]; then
    echo "$HOME/.pi/agent/AGENTS.md|$HOME/.conventions/CONVENTIONS.md"
  fi
}

conventions_link_main() {
  shift  # discard 'user'
  shift  # discard 'conventions'
  local repo_root="$PWD"
  local dry_run=0
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo-root) repo_root="$2"; shift 2 ;;
      --dry-run)   dry_run=1; shift ;;
      *) echo "unknown flag: $1" >&2; return 2 ;;
    esac
  done

  _conventions_link_layer2 "$repo_root" "$dry_run" || return 1
  _conventions_link_layer3 "$dry_run" || return 1
}

_conventions_link_layer3() {
  local dry_run="$1"
  local slot target
  while IFS='|' read -r slot target; do
    [ -n "$slot" ] || continue
    # Ensure the slot's parent directory exists (defensive — _slots() already
    # gates on directory existence, but a slot path might need an intermediate
    # subdirectory).
    [ "$dry_run" -eq 1 ] || mkdir -p "$(dirname "$slot")"
    _conventions_maybe_link "$slot" "$target" "$dry_run" || return 1
  done < <(_conventions_layer3_slots)
}

# Idempotent: skip if correct, replace if stale, create if missing.
_conventions_link_layer2() {
  local repo_root="$1"
  local dry_run="$2"
  if [ -e "$HOME/.conventions" ] && [ ! -d "$HOME/.conventions" ] && [ ! -L "$HOME/.conventions" ]; then
    echo "error: $HOME/.conventions exists and is not a directory — refuses to proceed" >&2
    return 1
  fi
  [ "$dry_run" -eq 1 ] || mkdir -p "$HOME/.conventions"
  _conventions_maybe_link \
    "$HOME/.conventions/CONVENTIONS.md" \
    "$repo_root/CONVENTIONS.md" \
    "$dry_run" || return 1
  _conventions_maybe_link \
    "$HOME/.conventions/conventions" \
    "$repo_root/conventions" \
    "$dry_run" || return 1
}

# Create or replace a symlink. Idempotent.
_conventions_maybe_link() {
  local link_path="$1"
  local target="$2"
  local dry_run="$3"
  if [ -L "$link_path" ] && [ "$(readlink "$link_path")" = "$target" ]; then
    return  # already correct
  fi
  if [ -e "$link_path" ] && [ ! -L "$link_path" ]; then
    echo "error: $link_path exists and is not a symlink — refuses to overwrite" >&2
    return 1
  fi
  if [ "$dry_run" -eq 1 ]; then
    echo "would-link: $link_path -> $target"
    return
  fi
  rm -f "$link_path"
  ln -s "$target" "$link_path"
  echo "linked: $link_path -> $target"
}

conventions_unlink_main() {
  shift  # discard 'user'
  shift  # discard 'conventions'
  local dry_run=0
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo-root) shift 2 ;;       # accepted for symmetry, ignored
      --dry-run)   dry_run=1; shift ;;
      *) echo "unknown flag: $1" >&2; return 2 ;;
    esac
  done

  local slot target
  while IFS='|' read -r slot target; do
    [ -L "$slot" ] || continue
    # Only remove if the symlink's target is the Layer 2 path we own.
    [ "$(readlink "$slot")" = "$target" ] || continue
    if [ "$dry_run" -eq 1 ]; then
      echo "would-unlink: $slot"
    else
      rm "$slot"
      echo "unlinked: $slot"
    fi
  done < <(_conventions_layer3_slots)
}

conventions_list_main() {
  shift; shift
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo-root) shift 2 ;;       # accepted, ignored
      *) echo "unknown flag: $1" >&2; return 2 ;;
    esac
  done

  # Layer 2
  if [ -L "$HOME/.conventions/CONVENTIONS.md" ]; then
    local l2_target
    l2_target="$(readlink "$HOME/.conventions/CONVENTIONS.md")"
    echo "layer2: $HOME/.conventions/CONVENTIONS.md -> $l2_target"
  fi
  if [ -L "$HOME/.conventions/conventions" ]; then
    local l2_dir_target
    l2_dir_target="$(readlink "$HOME/.conventions/conventions")"
    echo "layer2: $HOME/.conventions/conventions -> $l2_dir_target"
  fi

  # Layer 3
  local slot target
  while IFS='|' read -r slot target; do
    if [ -L "$slot" ]; then
      local immediate resolved
      immediate="$(readlink "$slot")"
      resolved="$(_conventions_resolve "$slot")"
      echo "layer3: $slot -> $immediate -> $resolved"
    fi
  done < <(_conventions_layer3_slots)
}

# Resolve a symlink chain to its final real path. Avoids `readlink -f`
# because BSD readlink (older macOS) doesn't support it. Uses a small loop
# with a 32-iteration cap to defend against symlink cycles.
_conventions_resolve() {
  local path="$1"
  local i=0
  while [ -L "$path" ] && [ "$i" -lt 32 ]; do
    local target
    target="$(readlink "$path")"
    case "$target" in
      /*) path="$target" ;;
      *)  path="$(dirname "$path")/$target" ;;
    esac
    i=$((i + 1))
  done
  echo "$path"
}

conventions_diff_main() {
  # Re-dispatch as link --dry-run, preserving any --repo-root caller passed.
  shift; shift  # discard 'user' 'conventions'
  conventions_link_main "user" "conventions" --dry-run "$@"
}
