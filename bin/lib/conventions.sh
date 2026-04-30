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
  # Args: <user> conventions [--repo-root DIR] [--dry-run]
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
  echo "stub: would link conventions from $repo_root (dry_run=$dry_run)"
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
