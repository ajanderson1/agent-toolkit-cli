# audit/lib/sandbox.sh — ephemeral sandbox HOME for audit demos.
#
# Usage:
#   source audit/lib/sandbox.sh
#   sandbox::init           # mutates env, registers EXIT trap
#   sandbox::cleanup        # callable manually; trap calls it on exit
#
# SANDBOX_DEFAULT_TOOLKIT_REPO is captured at source-time (before sandbox::init
# mutates HOME), so the fallback path resolves against the real HOME.

SANDBOX_DEFAULT_TOOLKIT_REPO="${AGENT_TOOLKIT_REPO:-$HOME/GitHub/agent-toolkit}"

sandbox::init() {
  sandbox::cleanup
  local tmp
  tmp="$(mktemp -d -t agent-toolkit-audit.XXXXXX)"
  export SANDBOX_TMPDIR="$tmp"
  export HOME="$tmp"
  export XDG_CONFIG_HOME="$tmp/.config"
  export CLAUDE_CONFIG_DIR="$tmp/.claude"
  export CODEX_HOME="$tmp/.codex"
  # OpenCode/Gemini/Pi: HOME redirection is the universal fallback.
  # If empirical testing in later tasks shows a harness needs a dedicated
  # var, add it here.
  export AGENT_TOOLKIT_REPO="$SANDBOX_DEFAULT_TOOLKIT_REPO"
  mkdir -p "$XDG_CONFIG_HOME" "$CLAUDE_CONFIG_DIR" "$CODEX_HOME"
  trap 'sandbox::cleanup' EXIT
}

sandbox::cleanup() {
  if [ -n "${SANDBOX_TMPDIR:-}" ] && [ -d "$SANDBOX_TMPDIR" ]; then
    rm -rf "$SANDBOX_TMPDIR"
  fi
  unset SANDBOX_TMPDIR
}
