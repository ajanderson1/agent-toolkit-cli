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

  _conventions_link_layer2 "$repo_root" "$dry_run"
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
  shift; shift
  echo "stub: would unlink conventions"
}

conventions_list_main() {
  shift; shift
  echo "stub: would list conventions"
}

conventions_diff_main() {
  shift; shift
  echo "stub: would diff conventions"
}
