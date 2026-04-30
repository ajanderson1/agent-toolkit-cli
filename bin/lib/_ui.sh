# shellcheck shell=bash
# Tiny output helper — header before a command's main work, summary after.
# Honours AGENT_TOOLKIT_QUIET=1 so tests and pipes can suppress chrome.

_ui_header() {
  [ "${AGENT_TOOLKIT_QUIET:-0}" = "1" ] && return 0
  printf '%s\n' "$*" >&2
}

_ui_summary() {
  [ "${AGENT_TOOLKIT_QUIET:-0}" = "1" ] && return 0
  printf '%s\n' "$*" >&2
}
