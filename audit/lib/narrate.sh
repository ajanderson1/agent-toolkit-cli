# audit/lib/narrate.sh — paced narration helpers for audit demos.
#
# step <heading>             # bold heading + newline
# run  <cmd>                 # echo command, then eval it
# show <path>                # ls -la + readlink (symlink) or head -20 (file)
# pause <seconds>            # sleep, scaled by $PAUSE_SCALE (default 1)

_narrate_bold() {
  if [ -t 1 ]; then
    printf '\033[1m%s\033[0m\n' "$1"
  else
    printf '%s\n' "$1"
  fi
}

step() {
  printf '\n'
  _narrate_bold "# $*"
}

run() {
  _narrate_bold "$ $*"
  eval "$@"
}

show() {
  local path="$1"
  if [ ! -e "$path" ] && [ ! -L "$path" ]; then
    printf '  MISSING: %s\n' "$path"
    return 0
  fi
  ls -la "$path"
  if [ -L "$path" ]; then
    printf '  -> %s\n' "$(readlink "$path")"
  elif [ -f "$path" ]; then
    head -20 "$path"
  fi
}

pause() {
  local seconds="$1"
  local scale="${PAUSE_SCALE:-1}"
  # POSIX sh has no float arithmetic; rely on awk.
  local actual
  actual="$(awk -v s="$seconds" -v k="$scale" 'BEGIN { print s * k }')"
  # Skip the sleep entirely if scale is 0.
  if [ "$scale" = "0" ]; then
    return 0
  fi
  sleep "$actual"
}
