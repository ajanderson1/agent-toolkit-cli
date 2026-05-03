# shellcheck shell=bash
# Common helpers for agent-toolkit bash subcommands.

# Map (harness, kind) → user-scope target directory under $HOME.
# Empty string means "not supported by this harness."
harness_target_dir() {
  local harness="$1"
  local kind="$2"
  case "$harness:$kind" in
    claude:skill)    echo "$HOME/.claude/skills" ;;
    claude:agent)    echo "$HOME/.claude/agents" ;;
    claude:command)  echo "$HOME/.claude/commands" ;;
    claude:hook)     echo "$HOME/.claude/hooks" ;;
    claude:plugin)   echo "$HOME/.claude/plugins" ;;
    codex:skill)     echo "$HOME/.codex/skills" ;;
    opencode:skill)  echo "$HOME/.config/opencode/skills" ;;
    pi:skill)        echo "$HOME/.pi/agent/skills" ;;
    pi:agent)        echo "$HOME/.pi/agent/agents" ;;
    pi:plugin)       echo "$HOME/.pi/agent/extensions" ;;
    *)               echo "" ;;
  esac
}

# Map (harness, kind) → project-scope target directory relative to PROJECT_ROOT.
project_target_dir() {
  local harness="$1"
  local kind="$2"
  case "$harness:$kind" in
    claude:skill)    echo ".claude/skills" ;;
    claude:agent)    echo ".claude/agents" ;;
    claude:command)  echo ".claude/commands" ;;
    claude:hook)     echo ".claude/hooks" ;;
    claude:plugin)   echo ".claude/plugins" ;;
    codex:skill)     echo ".codex/skills" ;;
    opencode:skill)  echo ".opencode/skills" ;;
    pi:skill)        echo ".pi/agent/skills" ;;
    pi:agent)        echo ".pi/agent/agents" ;;
    pi:plugin)       echo ".pi/agent/extensions" ;;
    *)               echo "" ;;
  esac
}

# Read spec.harnesses from a YAML frontmatter file. Prints one harness per line.
# Uses awk + sed so we don't depend on yq.
read_harnesses_from_frontmatter() {
  local file="$1"
  awk '
    /^---$/ { count++; if (count == 2) exit; next }
    count == 1 && /^[[:space:]]*harnesses:/ { in_harnesses = 1; next }
    count == 1 && /^[[:space:]]*[a-z_]+:/ && !/^[[:space:]]*-/ { in_harnesses = 0 }
    count == 1 && in_harnesses && /^[[:space:]]*-[[:space:]]+(claude|codex|opencode|pi)[[:space:]]*$/ {
      gsub(/^[[:space:]]*-[[:space:]]+/, "")
      gsub(/[[:space:]]+$/, "")
      print
    }
  ' "$file"
}

# Walk a directory of slug-named subdirs and yield "kind:slug:metadata-file-path"
# triples on stdout, one per line.
discover_assets_for_kind() {
  local toolkit_root="$1"
  local kind="$2"
  local root_dir
  case "$kind" in
    skill)   root_dir="$toolkit_root/skills" ;;
    agent)   root_dir="$toolkit_root/agents" ;;
    command) root_dir="$toolkit_root/commands" ;;
    hook)    root_dir="$toolkit_root/hooks" ;;
    mcp)     root_dir="$toolkit_root/mcps" ;;
    plugin)  root_dir="$toolkit_root/plugins" ;;
    *)       return ;;
  esac
  [ -d "$root_dir" ] || return
  case "$kind" in
    skill|mcp|plugin)
      local pattern
      case "$kind" in
        skill)  pattern="SKILL.md" ;;
        mcp)    pattern="mcp.json" ;;
        plugin) pattern="marketplace.json" ;;
      esac
      find "$root_dir" -type f -name "$pattern" -print | sort | while read -r file; do
        local slug
        slug="$(basename "$(dirname "$file")")"
        echo "${kind}:${slug}:${file}"
      done
      ;;
    agent|command)
      find "$root_dir" -type f -name "*.md" -print | sort | while read -r file; do
        local slug
        slug="$(basename "$file" .md)"
        echo "${kind}:${slug}:${file}"
      done
      ;;
    hook)
      find "$root_dir" -type f -name "*.meta.yaml" -print | sort | while read -r file; do
        local slug
        slug="$(basename "$file" .meta.yaml)"
        echo "${kind}:${slug}:${file}"
      done
      ;;
  esac
}

# Map an asset kind to its allow-list section name.
# Errors on `mcp` (not scope-routed) or unknown kinds.
kind_to_section() {
  local kind="$1"
  case "$kind" in
    skill)   echo "skills" ;;
    agent)   echo "agents" ;;
    command) echo "commands" ;;
    hook)    echo "hooks" ;;
    plugin)  echo "plugins" ;;
    mcp)     echo "mcps are not yet scope-routed — edit the harness's mcp.json directly" >&2; return 2 ;;
    *)       echo "unknown asset kind: $kind" >&2; return 2 ;;
  esac
}

# Read all slugs in a single section of an allow-list YAML file. Prints one
# slug per line on stdout. Empty if the file or section is missing.
# Handles both inline (`skills: [a, b]`) and multi-line dash forms.
read_allowlist_section() {
  local file="$1"
  local section="$2"
  [ -f "$file" ] || return 0
  awk -v sect="$section:" '
    BEGIN { in_sect = 0 }
    # New top-level key — leave the section we were in
    /^[a-z][a-z_]*:/ {
      if (in_sect) { in_sect = 0 }
      if ($0 ~ "^"sect) {
        in_sect = 1
        # Inline form? "skills: [a, b]"
        rest = $0
        sub("^"sect"[[:space:]]*", "", rest)
        if (rest ~ /^\[/) {
          sub(/[[:space:]]*#.*/, "", rest)
          gsub(/[\[\],]/, " ", rest)
          n = split(rest, parts, /[[:space:]]+/)
          for (i = 1; i <= n; i++) {
            if (parts[i] != "") print parts[i]
          }
          in_sect = 0
        }
        next
      }
    }
    # Nested mapping inside an active section terminates it
    in_sect && /^[[:space:]]+[a-z][a-z_]*:/ {
      in_sect = 0
    }
    # Multi-line dash form: "  - slug" (indented) or "- slug" (column 0, ruamel offset=0)
    in_sect && /^[[:space:]]*-[[:space:]]+/ {
      line = $0
      sub(/^[[:space:]]*-[[:space:]]+/, "", line)
      sub(/[[:space:]]+#.*/, "", line)   # strip inline comment
      sub(/[[:space:]]+$/, "", line)
      if (line != "") print line
    }
  ' "$file"
}

# True (exit 0) iff stdin and stdout are both attached to a TTY.
# Used by `link --all` to decide whether to prompt.
have_tty() {
  [ -t 0 ] && [ -t 1 ]
}

# Resolve the agent-toolkit SSOT root via the four-step order:
#   1. --toolkit-repo <path>   (caller passed via $1)
#   2. $AGENT_TOOLKIT_REPO     (env)
#   3. walk up from $PWD looking for .agent-toolkit-source
#   4. ~/GitHub/agent-toolkit  (default)
# Echoes the resolved path on success. On failure, prints an actionable
# message to stderr and returns 2.
resolve_toolkit_root() {
  local explicit="${1:-}"
  local marker=".agent-toolkit-source"
  local schema="schemas/asset-frontmatter.v1alpha1.json"

  _is_toolkit_repo() {
    [ -d "$1" ] && [ -f "$1/$schema" ] && [ -f "$1/$marker" ]
  }

  if [ -n "$explicit" ]; then
    if _is_toolkit_repo "$explicit"; then
      echo "$explicit"
      return 0
    fi
    echo "--toolkit-repo $explicit is not a valid agent-toolkit repo (missing $marker or $schema)." >&2
    return 2
  fi

  if [ -n "${AGENT_TOOLKIT_REPO:-}" ]; then
    if _is_toolkit_repo "$AGENT_TOOLKIT_REPO"; then
      echo "$AGENT_TOOLKIT_REPO"
      return 0
    fi
    echo "AGENT_TOOLKIT_REPO=$AGENT_TOOLKIT_REPO is not a valid agent-toolkit repo." >&2
    return 2
  fi

  local cur
  cur="$(pwd -P)"
  while :; do
    if [ -f "$cur/$marker" ] && [ -f "$cur/$schema" ]; then
      echo "$cur"
      return 0
    fi
    [ "$cur" = "/" ] && break
    cur="$(dirname "$cur")"
  done

  local default="$HOME/GitHub/agent-toolkit"
  if _is_toolkit_repo "$default"; then
    echo "$default"
    return 0
  fi

  cat >&2 <<EOF
Cannot find an agent-toolkit repo. Tried:
  --toolkit-repo flag: not provided
  \$AGENT_TOOLKIT_REPO: ${AGENT_TOOLKIT_REPO:-(unset)}
  walk-up from $(pwd -P): no $marker marker found
  default $default: missing or invalid

Install the toolkit repo: git clone https://github.com/ajanderson1/agent-toolkit ~/GitHub/agent-toolkit
Or pass --toolkit-repo <path> / set AGENT_TOOLKIT_REPO.
Install the CLI: uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli agent-toolkit
EOF
  return 2
}
