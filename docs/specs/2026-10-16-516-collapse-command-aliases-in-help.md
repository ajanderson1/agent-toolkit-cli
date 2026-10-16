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
- Present subcommands sharing a single `Command` object instance as a single combined entry in the help menu: `canonical, alias1, ...` (e.g., `list, ls` and `remove, rm`).
- Ensure the canonical command name (as defined on `Command.name` if present in the visible registered names, with deterministic first-visible fallback) appears first.
- Ensure distinct `Command` objects that share a callback function remain separate and are not falsely collapsed.
- Preserve hidden commands and hidden aliases: any command with `cmd.hidden = True` is excluded from help output.
- Preserve top-level `main --help` formatting (`AssetCommandGroup` remains a standard Click group; only asset groups with aliases use the aliased formatter).
- Maintain Click's column width calculations and formatting so docstrings align cleanly, even under narrow terminal widths.
- Ensure all command names and aliases continue to execute identically with all options and arguments.
- Ensure invoking `--help` on any alias (e.g. `pi-extension ls --help`) continues to work as expected.
- Maintain full compatibility with plural group aliases (`skills`, `agents`, `mcps`, `pi-extensions`, `commands`).

### Non-Goals
- Changing the names, options, or behaviors of any subcommands.
- Removing any registered aliases or altering how subcommands are dispatched.
- Modifying how top-level asset groups are displayed in `main --help`.
- Grouping unrelated commands by callback identity (explicitly rejected to prevent false collisions).

## 3. Technical Design

### 3.1 `AliasedGroup` in `src/agent_toolkit_cli/_group.py`
Introduce a reusable `AliasedGroup(click.Group)` that overrides `format_commands(ctx, formatter)`:
1. Iterate over `self.list_commands(ctx)` to retrieve each subcommand via `self.get_command(ctx, subcommand)`.
2. Skip commands that are `None` or marked `cmd.hidden`.
3. Group subcommands strictly by Command object identity: `cmd_id = id(cmd)`. This guarantees that distinct `Command` objects sharing a callback function remain separate, while registered aliases (which pass the identical `Command` instance) are collapsed.
4. For each grouped set of visible names:
   - Identify the canonical name: `cmd.name` if `cmd.name` is present in the visible registered names; otherwise fall back deterministically to the first visible name in `list_commands(ctx)`.
   - Sort the remaining aliases alphabetically: `sorted(name for name in names if name != canonical)`.
   - Format the display label: `f"{canonical}, {', '.join(aliases)}"` if aliases exist, otherwise `canonical`.
5. Sort rows alphabetically by canonical name (`rows_data.sort(key=lambda item: item[0])`).
6. Calculate Click formatter column limit using `formatter.width - 6 - max_label_len`.
7. Write the formatted definitions using `formatter.write_dl(rows)` inside a `"Commands"` section.

### 3.2 Update Command Groups
Configure `cls=AliasedGroup` on all asset groups that define aliases:
- `pi_extension` in `src/agent_toolkit_cli/commands/pi_extension/__init__.py`.
- `skill` in `src/agent_toolkit_cli/commands/skill/__init__.py`.
- `agent` in `src/agent_toolkit_cli/commands/agent/__init__.py`.
- `mcp` in `src/agent_toolkit_cli/commands/mcp/__init__.py`.
- `command` in `src/agent_toolkit_cli/commands/command/__init__.py`.
- Unaliased groups (`bundle`, `instructions`) remain standard `@click.group` without modification.
- Top-level `AssetCommandGroup` in `cli.py` remains standard `click.Group` to preserve the canonical plural top-level presentation.

## 4. Verification & Testing

1. **Unit & Help Tests (`tests/test_cli/test_cli_group_aliases_help.py`):**
   - Verify `AliasedGroup` collapses identical Command objects into `list, ls` on one row without duplicate rows.
   - Verify distinct Command objects sharing the same callback function remain separate and are not collapsed.
   - Verify hidden commands/aliases are not rendered.
   - Verify canonical name comes first when visible, with deterministic first-visible fallback when `cmd.name` is absent or different.
   - Verify narrow width formatting does not crash and wraps properly.
   - Verify `pi-extension --help`, `skill --help`, `agent --help`, `mcp --help`, and `command --help` output `list, ls` on a single row.
   - Verify `skill --help` outputs `remove, rm` on a single row.
   - Verify plural group help (`skills --help`, `pi-extensions --help`, etc.) matches.
   - Verify that groups without aliases (`bundle --help`, `instructions --help`) continue to format normally.
   - Verify top-level `agent-toolkit-cli --help` formatting is unchanged.
2. **Behavioral Integrity:**
   - Verify running `agent-toolkit-cli pi-extension ls` and `agent-toolkit-cli skill rm` behaves identically to before.
   - Verify running `agent-toolkit-cli pi-extension ls --help` exits 0.
   - Verify all existing alias tests in `test_cli_skill_aliases.py` and `test_command_coverage_guard.py` remain green.
