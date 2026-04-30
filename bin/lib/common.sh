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
  local repo_root="$1"
  local kind="$2"
  local root_dir
  case "$kind" in
    skill)   root_dir="$repo_root/skills" ;;
    agent)   root_dir="$repo_root/agents" ;;
    command) root_dir="$repo_root/commands" ;;
    hook)    root_dir="$repo_root/hooks" ;;
    mcp)     root_dir="$repo_root/mcps" ;;
    plugin)  root_dir="$repo_root/plugins" ;;
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
