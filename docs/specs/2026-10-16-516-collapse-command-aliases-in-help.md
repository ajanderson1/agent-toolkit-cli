Issue: #516
# Spec: Collapse Command Aliases into Single Entries in Group Help Menus

## 1. Intent & Context

The `agent-toolkit-cli` tool manages various asset kinds (skills, agents, MCPs, pi-extensions, commands, bundles, instructions). Several of these command groups register aliases for commonly used verbs to accommodate user habits and muscle memory (e.g., `ls` as an alias for `list` across `pi-extension`, `skill`, `agent`, `mcp`, and `command`; `rm` as an alias for `remove` in `skill`).

Currently, Click's default `click.Group.format_commands` method iterates over every name returned by `list_commands(ctx)` individually. Because each alias is registered as an additional command name in the group, Click renders duplicate rows in the `--help` output:

```text
Commands:
  list       List every Pi extension the toolkit can see (library,...
  ls         List every Pi extension the toolkit can see (library,...
```

and for skills:

```text
  list       List installed skills from the lock file.
  ls         List installed skills from the lock file.
  remove     Remove selected skills from the library.
  rm         Remove selected skills from the library.
```

This pollutes the help menu, creates unnecessary visual noise, and obscures the distinct verbs available to the user.

## 2. Goals & Non-Goals

### Goals
- Present subcommands sharing a callback or command object as a single combined entry in the help menu: `canonical, alias1, ...` (e.g., `list, ls` and `remove, rm`).
- Ensure the canonical command name (as defined on `Command.name` or longest form) appears first.
- Maintain Click's column width calculations so docstrings align cleanly.
- Ensure all command names and aliases continue to execute identically with all options and arguments.
- Ensure invoking `--help` on any alias (e.g. `pi-extension ls --help`) continues to work as expected.
- Maintain full compatibility with `AssetCommandGroup` and plural group aliases (`skills`, `agents`, `mcps`, `pi-extensions`, `commands`).

### Non-Goals
- Changing the names, options, or behaviors of any subcommands.
- Removing any registered aliases or altering how subcommands are dispatched.
- Modifying how top-level asset groups are displayed in `main --help` (which already displays plural canonical names).

## 3. Technical Design

### 3.1 `AliasedGroup` in `src/agent_toolkit_cli/_group.py`
Introduce a reusable `AliasedGroup(click.Group)` that overrides `format_commands(ctx, formatter)`:
1. Iterate over `self.list_commands(ctx)` to retrieve each subcommand via `self.get_command(ctx, subcommand)`.
2. Skip commands that are `None` or marked `cmd.hidden`.
3. Group subcommands by identity / callback key: `getattr(cmd, "callback", None) or id(cmd)`.
4. For each grouped set:
   - Identify the canonical name: `cmd.name` if present in the aliases list, otherwise the first registered or longest name.
   - Sort the remaining aliases alphabetically.
   - Format the display label: `", ".join([canonical] + sorted(aliases))`.
5. Recalculate Click formatter column limit using `max(len(label) for label, _ in formatted_entries)`.
6. Write the formatted definitions using `formatter.write_dl(rows)` inside a `"Commands"` section.

### 3.2 Update Command Groups
Configure `cls=AliasedGroup` on all asset groups:
- `AssetCommandGroup` in `src/agent_toolkit_cli/cli.py` inherits from `AliasedGroup`.
- `pi_extension` in `src/agent_toolkit_cli/commands/pi_extension/__init__.py`.
- `skill` in `src/agent_toolkit_cli/commands/skill/__init__.py`.
- `agent` in `src/agent_toolkit_cli/commands/agent/__init__.py`.
- `mcp` in `src/agent_toolkit_cli/commands/mcp/__init__.py`.
- `command` in `src/agent_toolkit_cli/commands/command/__init__.py`.
- `bundle` in `src/agent_toolkit_cli/commands/bundle/__init__.py`.
- `instructions` in `src/agent_toolkit_cli/commands/instructions/__init__.py`.

## 4. Verification & Testing

1. **Unit & Help Tests (`tests/test_cli/test_cli_group_aliases_help.py`):**
   - Verify `pi-extension --help` outputs `list, ls` on a single row and does not have a separate `ls` row.
   - Verify `skill --help` outputs `list, ls` and `remove, rm` on single rows without standalone `ls` or `rm` rows.
   - Verify `agent --help`, `mcp --help`, and `command --help` output `list, ls`.
   - Verify plural group help (`skills --help`, `pi-extensions --help`, etc.) matches.
   - Verify that groups without aliases (`bundle --help`, `instructions --help`) continue to format normally.
2. **Behavioral Integrity:**
   - Verify running `agent-toolkit-cli pi-extension ls` and `agent-toolkit-cli skill rm` behaves identically to before.
   - Verify running `agent-toolkit-cli pi-extension ls --help` exits 0.
   - Verify all existing alias tests in `test_cli_skill_aliases.py` and `test_command_coverage_guard.py` remain green.
