# shellcheck shell=bash

diff_main() {
  # diff is just `link --dry-run`
  # shellcheck source=link.sh
  . "$(dirname "${BASH_SOURCE[0]}")/link.sh"
  link_main "$@" --dry-run
}
