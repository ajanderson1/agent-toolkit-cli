# Shell completion

Toolkit provides **dynamic TAB completion** using Click's shell-completion
protocol. It works for the packaged short names **`atc` / `att`** and their
long forms **`agent-toolkit-cli` / `agent-toolkit-tui`**.

The executables themselves need no shell aliases. Completion needs a one-time
shell integration, much like Worktrunk's `wt` setup. Installing/updating the
Toolkit package alone does **not** modify your shell startup files.

## What completes

| Input | Completion |
|---|---|
| `atc sk` + TAB | Matching top-level commands such as `skills`. |
| `atc skills in` + TAB | Matching verbs such as `install`; singular group aliases also resolve. |
| `atc update --` + TAB | Flags such as `--check` and `--main`. |
| `atc instructions list --format j` + TAB | Declared choice values such as `json`. |
| `atc --project /some/path` + TAB | Native shell directory/path completion for a declared path argument. |
| `att up` + TAB | `update`, without starting the TUI. |

Only declared choice/path types provide value completion. Arbitrary strings,
comma-separated harness lists, asset slugs, catalogue keys and remote repository
names are **not dynamically discovered**. Completion does not fetch repositories,
check for application updates, apply asset changes, or open the TUI.

## Automatic setup

The same utility is available as `atc completion` and `att completion` (and both
long names). Supported shells are **Zsh**, **Bash 4.4+**, and **Fish**.

### Zsh

```bash
atc completion install --shell zsh
source ~/.zshrc
```

Use the path printed by the command if you have a custom `ZDOTDIR` or `--rc-file`.
Opening a new terminal also loads the integration. The block initializes
`compinit` only when the completion system is not already available; it does not
replace existing `wt` or other completion setup.

### Bash

```bash
atc completion install --shell bash
source ~/.bashrc
```

For login shells, ensure your `~/.bash_profile` sources `~/.bashrc`. macOS's
system Bash 3.2 is too old for this completion integration: use Zsh or a newer
Bash. Setup does not upgrade your shell.

### Fish

```fish
atc completion install --shell fish
```

Open a new Fish session, or source the configuration path printed by the command.
The default is `~/.config/fish/conf.d/agent-toolkit-completion.fish` unless
`XDG_CONFIG_HOME` selects another configuration root.

### Options and default paths

```text
atc completion install [--shell zsh|bash|fish] [--rc-file PATH]
atc completion uninstall [--shell zsh|bash|fish] [--rc-file PATH]
atc completion init zsh|bash|fish
```

| Shell | Default startup file |
|---|---|
| Zsh | `$ZDOTDIR/.zshrc`, or `~/.zshrc` when `ZDOTDIR` is unset. |
| Bash | `~/.bashrc`. |
| Fish | `$XDG_CONFIG_HOME/fish/conf.d/agent-toolkit-completion.fish`, or `~/.config/fish/conf.d/agent-toolkit-completion.fish`. |

Omitting `--shell` detects the name from **`$SHELL`**, which normally identifies
your login shell, not necessarily a nested shell you are currently using.
Unsupported/missing values require an explicit `--shell`; there is no OS-based
guess. `init` always requires its shell argument and only prints source code.

For a custom dotfile location:

```bash
atc completion install --shell zsh --rc-file ~/.config/zsh/custom.zsh
source ~/.config/zsh/custom.zsh
```

Use the **same `--shell` and `--rc-file`** when removing that integration. The
custom file must itself be sourced by your shell; setup does not edit a different
startup file to make it load.

## Exactly what setup changes

`install` appends or updates one marked region. For Zsh it is:

```zsh
# >>> agent-toolkit completion >>>
if command -v atc >/dev/null 2>&1; then
    if ! (( $+functions[compdef] )); then
        autoload -Uz compinit && compinit
    fi
    eval "$(command atc completion init zsh)"
fi
# <<< agent-toolkit completion <<<
```

- Repeated setup is **idempotent**: it updates this block rather than adding
  duplicates. It registers completion, not `atc`/`att` aliases or directory-changing
  wrappers.
- Unrelated file text and existing permissions are retained. A symlinked dotfile
  remains a symlink; its resolved target receives the atomic file replacement.
- An absent file/parent directory is created by `install`. `uninstall` does not
  create missing configuration. No application behavior or asset settings change.
- Incomplete, duplicated, malformed or out-of-order markers cause a refusal.
  Inspect the file manually rather than letting setup guess which text to remove.
- The shipped installer **does not create a backup file**. The managed block is
  reversible; make your own backup first if you want an original-byte recovery
  point for a customized shell configuration.

The block loads code from the installed `atc` on shell startup. As with any
`eval`/`source` integration, only use an executable whose package/source you
trust. [Verify the Toolkit installation](installation.md#verify-a-published-wheel).

## How dynamic completion works

1. `completion init SHELL` generates Click's shell functions for all four
   executable names. Zsh registers these with `compdef`; Bash and Fish use their
   native registration mechanisms.
2. Pressing TAB passes the command line and cursor position to the corresponding
   executable in Click's completion mode.
3. Click parses the current command tree without invoking command callbacks and
   returns matching commands, options, descriptions, or choice values. The shell
   handles native path suggestions.
4. The TUI launcher is also a Click dispatcher, so completion can inspect its
   `update` and `completion` commands without constructing/running the TUI.

The internal completion request variables are:

| Executable | Variable |
|---|---|
| `atc` | `_ATC_COMPLETE` |
| `agent-toolkit-cli` | `_AGENT_TOOLKIT_CLI_COMPLETE` |
| `att` | `_ATT_COMPLETE` |
| `agent-toolkit-tui` | `_AGENT_TOOLKIT_TUI_COMPLETE` |

These are **protocol variables**, not settings to export permanently. The
integration sets them only for individual requests. Zsh/Bash also pass
`COMP_WORDS` and `COMP_CWORD`; Fish uses Click's corresponding Fish protocol.

This is not a static list of every command. TAB requests query the current
executable, so new commands become available after a package update without
regenerating a command catalogue. Previously loaded shell functions can be
refreshed by opening a new terminal or sourcing your setup again.

Implementation: `src/agent_toolkit_cli/commands/completion.py`, the CLI command
tree, and `src/agent_toolkit_tui/launcher.py`. No third-party shell plugin is
required beyond the supported shell's own completion system.

## Manual integration instead of managed setup

Choose **one** approach; do not load both managed and manual setup.

Zsh:

```zsh
autoload -Uz compinit && compinit
eval "$(command atc completion init zsh)"
```

Bash:

```bash
eval "$(command atc completion init bash)"
```

Fish:

```fish
command atc completion init fish | source
```

`init` does not write configuration. Loading its output changes functions in the
current shell only; put your chosen snippet in the correct startup file for
future sessions.

## Remove completion

```bash
atc completion uninstall --shell zsh
```

Use `bash` or `fish` for those shells, and repeat any custom `--rc-file` used
at setup. This removes **only** Toolkit's marked region. It does not delete
unrelated configuration, the package, assets, user-authored aliases, or manually
added integration. Open a new shell to clear functions already loaded in the
current process.

## Troubleshooting

| Symptom | Check |
|---|---|
| `completion` or `atc` is unknown | Upgrade a pre-7.1.0 client and check [PATH/command resolution](installation.md#command-not-found-or-wrong-version). |
| TAB does nothing | Open a new shell or source the exact file printed during setup; confirm you selected the shell actually being used. |
| Zsh reports `compdef` missing with manual setup | Initialize `compinit` before evaluating the source. Managed Zsh setup does this when needed. |
| `compinit` warns about unsafe directories | Inspect and fix your completion-directory ownership/permissions. Toolkit does not disable Zsh's security checks. |
| Bash login sessions lack completion | Ensure `.bash_profile` sources `.bashrc`; verify Bash is at least 4.4. |
| Custom file or `ZDOTDIR` setup is ignored | Ensure the environment points at the right directory and your shell actually sources that file. |
| Commands resolve to an old alias/function | Inspect `type -a atc att` in Bash/Zsh and deliberately remove obsolete aliases from your own startup files. |
| Markers are rejected | Back up and inspect the named file; repair the single intended block before retrying. Do not delete unrelated text. |
| Asset names or comma-separated harness names are not suggested | Those string values are not dynamically discovered. Use the relevant `list`/`--help` command. |
| Old integration persists after uninstall | Start a new shell; removal does not unload functions from the current process. |

See also: [Installation](installation.md) · [Package updates](updates.md) ·
[CLI reference](cli.md) · [TUI reference](tui.md).
