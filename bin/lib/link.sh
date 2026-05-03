# shellcheck shell=bash
# Implements `agent-toolkit link <user|project> <harness> [...]`.

. "$(dirname "${BASH_SOURCE[0]}")/_ui.sh"
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Toolkit project root — needed so `uv run` finds pyproject.toml even when
# the user's CWD is elsewhere (e.g., during `link project`).
_AT_TOOLKIT_PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Action counters — populated by _maybe_link, read by link_main.
_LINK_CREATED=0
_LINK_UPDATED=0
_LINK_REMOVED=0
_LINK_UNCHANGED=0
_LINK_WOULD_LINK=0
_LINK_WOULD_UNLINK=0

# Resolve the path to the allow-list YAML for a given scope.
_link_allowlist_path() {
  case "$1" in
    user)    echo "$HOME/.agent-toolkit.yaml" ;;
    project) echo "$PWD/.agent-toolkit.yaml" ;;
    *)       echo ""; return 1 ;;
  esac
}

link_main() {
  local scope="$1"; shift
  local harness="$1"; shift
  local repo_root="$PWD"
  local dry_run=0
  local mode="bare"          # bare | per-asset | all
  local kind="" slug=""
  local assume_yes=0
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo-root) repo_root="$2"; shift 2 ;;
      --dry-run)   dry_run=1; shift ;;
      --quiet|-q)  AGENT_TOOLKIT_QUIET=1; shift ;;
      --all)
        if [ "$mode" = "per-asset" ]; then
          echo "cannot combine --all with $kind:$slug" >&2; return 2
        fi
        mode="all"
        shift
        ;;
      -y|--yes)    assume_yes=1; shift ;;
      *:*)
        if [ "$mode" = "all" ]; then
          echo "cannot combine --all with $1" >&2; return 2
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
  allowlist_path="$(_link_allowlist_path "$scope")"

  # Reset counters
  _LINK_CREATED=0; _LINK_UPDATED=0; _LINK_REMOVED=0
  _LINK_UNCHANGED=0; _LINK_WOULD_LINK=0; _LINK_WOULD_UNLINK=0

  case "$mode" in
    per-asset) _link_per_asset "$scope" "$harness" "$kind" "$slug" "$repo_root" "$allowlist_path" "$dry_run" ;;
    all)       _link_all "$scope" "$harness" "$repo_root" "$allowlist_path" "$assume_yes" "$dry_run" ;;
    bare)      _link_bare "$scope" "$harness" "$repo_root" "$allowlist_path" "$dry_run" ;;
  esac
}

# === Bare form ==============================================================
_link_bare() {
  local scope="$1" harness="$2" repo_root="$3" allowlist_path="$4" dry_run="$5"
  if [ ! -f "$allowlist_path" ]; then
    cat >&2 <<EOF
no $allowlist_path found.
  agent-toolkit link $scope $harness --all                  → snapshot every compatible asset, then project
  agent-toolkit link $scope $harness <kind>:<slug>          → add one asset, then project
  \$EDITOR $allowlist_path                                  → author by hand, then re-run
EOF
    return 2
  fi
  if [ "$dry_run" -eq 1 ]; then
    _ui_header "Previewing $scope-scope changes for $harness (no files will be modified)..."
  else
    _ui_header "Linking $scope-scope assets for $harness from $allowlist_path..."
  fi
  _link_project_from_file "$scope" "$harness" "$repo_root" "$allowlist_path" "$dry_run"
  _link_print_summary "$dry_run"
}

# === Per-asset form =========================================================
_link_per_asset() {
  local scope="$1" harness="$2" kind="$3" slug="$4"
  local repo_root="$5" allowlist_path="$6" dry_run="$7"

  # 1. mcp guard
  if [ "$kind" = "mcp" ]; then
    echo "mcps are not yet scope-routed — edit the harness's mcp.json directly" >&2
    return 2
  fi

  # 2. resolve asset
  local section
  section="$(kind_to_section "$kind")" || return 2
  local found_file=""
  while IFS=':' read -r _k _s _f; do
    if [ "$_s" = "$slug" ]; then found_file="$_f"; break; fi
  done < <(discover_assets_for_kind "$repo_root" "$kind")
  if [ -z "$found_file" ]; then
    echo "no $kind named '$slug' found. Run 'agent-toolkit list $kind' to see what's available." >&2
    return 1
  fi

  # 3. harness compatibility
  local harnesses
  harnesses=$(read_harnesses_from_frontmatter "$found_file" || true)
  if ! echo "$harnesses" | grep -qx "$harness"; then
    local declared
    declared=$(echo "$harnesses" | tr '\n' ',' | sed 's/,$//' | sed 's/,/, /g')
    echo "$kind:$slug doesn't support harness '$harness' (declares: ${declared:-none}). Use a different harness or pick another asset." >&2
    return 1
  fi

  # 4. mutate YAML (idempotent; creates file if missing).
  # Real run: write to allowlist_path. Dry-run: write to a temp file and
  # project from it, so the summary reflects what --add WOULD do.
  local target_path="$allowlist_path"
  local tmp_path=""
  if [ "$dry_run" -eq 1 ]; then
    tmp_path="$(mktemp -t agent-toolkit-add.XXXXXX)"
    if [ -f "$allowlist_path" ]; then
      cp "$allowlist_path" "$tmp_path"
    fi
    target_path="$tmp_path"
  fi

  uv run --project "$_AT_TOOLKIT_PROJECT" agent-toolkit _yaml-edit add "$target_path" "$section" "$slug" || {
    [ -n "$tmp_path" ] && rm -f "$tmp_path"
    return 1
  }

  # 5. project
  if [ "$dry_run" -eq 1 ]; then
    _ui_header "Previewing $scope-scope changes for $harness (no files will be modified)..."
  else
    _ui_header "Linking $scope-scope $kind:$slug for $harness..."
  fi
  _link_project_from_file "$scope" "$harness" "$repo_root" "$target_path" "$dry_run"
  [ -n "$tmp_path" ] && rm -f "$tmp_path"
  _link_print_summary "$dry_run"
}

# === --all form =============================================================
_link_all() {
  local scope="$1" harness="$2" repo_root="$3" allowlist_path="$4"
  local assume_yes="$5" dry_run="$6"

  # Confirm overwrite if file is populated
  if [ -f "$allowlist_path" ] && [ "$(_link_file_has_slugs "$allowlist_path")" = "1" ]; then
    if [ "$assume_yes" -ne 1 ]; then
      if ! have_tty; then
        echo "no TTY available — pass --yes/-y to confirm overwrite of existing $allowlist_path." >&2
        return 2
      fi
      local counts
      counts="$(_link_file_section_summary "$allowlist_path")"
      printf '%s already has %s.\n' "$allowlist_path" "$counts" >&2
      printf -- '--all will replace this with every compatible asset for %s.\n' "$harness" >&2
      printf 'Continue? [y/N] ' >&2
      local reply
      read -r reply
      case "$reply" in
        y|Y|yes|YES) ;;
        *) echo "aborted." >&2; return 2 ;;
      esac
    fi
  fi

  # Build the would-be snapshot. Real run writes to allowlist_path; dry-run
  # writes to a temp file and projects from that, so the summary reflects
  # what --all WOULD do.
  local target_path="$allowlist_path"
  local tmp_path=""
  if [ "$dry_run" -eq 1 ]; then
    tmp_path="$(mktemp -t agent-toolkit-snapshot.XXXXXX)"
    target_path="$tmp_path"
  fi

  {
    local kind
    for kind in skill agent command hook plugin; do
      local section
      section="$(kind_to_section "$kind")"
      while IFS=':' read -r _k _s _f; do
        local harnesses
        harnesses=$(read_harnesses_from_frontmatter "$_f" || true)
        if echo "$harnesses" | grep -qx "$harness"; then
          echo "$section $_s"
        fi
      done < <(discover_assets_for_kind "$repo_root" "$kind")
    done
  } | uv run --project "$_AT_TOOLKIT_PROJECT" agent-toolkit _yaml-edit snapshot "$target_path" || {
    [ -n "$tmp_path" ] && rm -f "$tmp_path"
    return 1
  }

  if [ "$dry_run" -eq 1 ]; then
    _ui_header "Previewing $scope-scope --all snapshot for $harness (no files will be modified)..."
  else
    _ui_header "Snapshotted every $harness-compatible asset into $allowlist_path; projecting..."
  fi
  _link_project_from_file "$scope" "$harness" "$repo_root" "$target_path" "$dry_run"
  [ -n "$tmp_path" ] && rm -f "$tmp_path"
  _link_print_summary "$dry_run"
}

# === Projection (shared) ====================================================
# Walks every kind, reads the section in the allow-list, projects only those
# slugs that also declare <harness>. Counts populated for the summary.
_link_project_from_file() {
  local scope="$1" harness="$2" repo_root="$3" allowlist_path="$4" dry_run="$5"
  local kind
  for kind in skill agent command hook plugin; do
    local target_dir
    if [ "$scope" = "user" ]; then
      target_dir="$(harness_target_dir "$harness" "$kind")"
    else
      target_dir="$(project_target_dir "$harness" "$kind")"
    fi
    [ -n "$target_dir" ] || continue
    [ "$dry_run" -eq 1 ] || mkdir -p "$target_dir"
    local section
    section="$(kind_to_section "$kind")"
    local allowed=" "
    while IFS= read -r s; do allowed+="$s "; done < <(read_allowlist_section "$allowlist_path" "$section")
    local discovered=" "
    while IFS=':' read -r _ slug file; do
      discovered+="$slug "
      if [[ "$allowed" == *" $slug "* ]]; then
        _maybe_link "$harness" "$kind" "$slug" "$file" "$target_dir" "$repo_root" "$dry_run"
      else
        # Asset not in allow-list — prune any existing symlink to this slug
        local link_path="$target_dir/$slug"
        if [ -L "$link_path" ]; then
          local target
          target="$(readlink "$link_path")"
          case "$target" in
            "$repo_root"/*)
              if [ "$dry_run" -eq 1 ]; then
                echo "would-unlink: $link_path"
                _LINK_WOULD_UNLINK=$((_LINK_WOULD_UNLINK + 1))
              else
                rm "$link_path"
                _LINK_REMOVED=$((_LINK_REMOVED + 1))
              fi
              ;;
          esac
        fi
      fi
    done < <(discover_assets_for_kind "$repo_root" "$kind")

    # Sweep: prune orphan symlinks (slug exists as symlink into repo but the
    # asset is gone from the toolkit). Keep symlinks that target outside the
    # repo (those belong to the user, not us).
    [ -d "$target_dir" ] || continue
    local entry
    for entry in "$target_dir"/*; do
      [ -L "$entry" ] || continue
      local entry_slug
      entry_slug="$(basename "$entry")"
      if [[ "$discovered" == *" $entry_slug "* ]]; then
        continue   # already handled above
      fi
      local target
      target="$(readlink "$entry")"
      case "$target" in
        "$repo_root"/*)
          if [ "$dry_run" -eq 1 ]; then
            echo "would-unlink: $entry"
            _LINK_WOULD_UNLINK=$((_LINK_WOULD_UNLINK + 1))
          else
            rm "$entry"
            _LINK_REMOVED=$((_LINK_REMOVED + 1))
          fi
          ;;
      esac
    done
  done
}

# === Helpers ================================================================
_link_file_has_slugs() {
  # Print "1" if any section in the file has at least one slug, else "0".
  local file="$1"
  [ -f "$file" ] || { echo 0; return; }
  local section
  for section in skills agents commands hooks plugins; do
    if [ -n "$(read_allowlist_section "$file" "$section")" ]; then
      echo 1; return
    fi
  done
  echo 0
}

_link_file_section_summary() {
  # "51 skills, 24 agents, 32 commands, 0 hooks, 0 plugins"
  local file="$1"
  local section
  local out=""
  for section in skills agents commands hooks plugins; do
    local n
    n=$(read_allowlist_section "$file" "$section" | wc -l | tr -d ' ')
    [ -z "$out" ] || out+=", "
    out+="$n $section"
  done
  echo "$out"
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

# _maybe_link — unchanged from previous version. Kept verbatim for clarity.
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
