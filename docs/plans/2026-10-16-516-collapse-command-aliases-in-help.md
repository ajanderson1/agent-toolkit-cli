# Collapse Command Aliases into Single Entries in Group Help Menus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Present aliased subcommands sharing a Command object as a single combined entry (e.g. `list, ls` and `remove, rm`) in Click group help menus across aliased toolkit asset kinds.
**Architecture:** Create an `AliasedGroup(click.Group)` in `src/agent_toolkit_cli/_group.py` that groups subcommands sharing a Command object identity into combined entries (`canonical, alias1, ...`) and calculates proper column spacing. Apply `AliasedGroup` to aliased asset command groups (`skill`, `pi_extension`, `agent`, `mcp`, `command`) while keeping unaliased groups (`bundle`, `instructions`) and top-level `AssetCommandGroup` unchanged.
**Tech Stack:** Python 3.9+, Click, pytest.
**Spec:** `docs/specs/2026-10-16-516-collapse-command-aliases-in-help.md`

## Global Constraints
- Python 3.9+ compatibility.
- Do not remove or rename any existing command or alias; dispatch and execution behavior must remain identical.
- Group strictly by `Command` object identity (`id(cmd)`), NOT by callback equality, ensuring distinct commands sharing a callback remain separate.
- Canonical command name (`cmd.name`) must appear first in combined help entries when visible; fallback deterministically to first visible name.
- Hidden commands (`cmd.hidden = True`) must remain hidden.
- Column indentation and alignment in Click help output must be preserved, including under narrow widths.
- Top-level `main --help` formatting must remain unchanged.
- All existing tests including coverage guards must pass cleanly under isolated synthetic environments.

## Review Focus
- Trailing or missing spacing in help formatting when aliases vary in length.
- Distinct Command objects sharing a callback remaining on separate lines.
- Groups without aliases (e.g., `bundle`, `instructions`) formatting identically to standard Click groups.
- Hidden subcommands (`cmd.hidden = True`) remaining hidden and not appearing as aliases.
- Individual alias `--help` invocation (e.g., `agent-toolkit-cli pi-extension ls --help`) continuing to work.
- Plural group aliases (`skills`, `agents`, `commands`, `mcps`, `pi-extensions`) properly inheriting `AliasedGroup` formatting.

---

### Task 1: Create `AliasedGroup` class with comprehensive unit tests

**Files:**
- Create: `src/agent_toolkit_cli/_group.py`
- Test: `tests/test_cli/test_cli_group_aliases_help.py`

**Interfaces:**
- Consumes: `click.Group`, `click.Context`, `click.HelpFormatter`
- Produces: `AliasedGroup` subclass of `click.Group` with overridden `format_commands(ctx, formatter)`

- [ ] **Step 1: Write failing unit tests for `AliasedGroup`**
  In `tests/test_cli/test_cli_group_aliases_help.py`, define tests covering:
  1. Identical Command object registered under multiple names (`list` and `ls`): displays `list, ls` on one row and no standalone `ls` row.
  2. Distinct Command objects sharing the same callback: remain on separate lines and are not collapsed.
  3. Canonical name ordering: `cmd.name` appears first when present in registered names; deterministic first visible fallback when `cmd.name` is absent or different.
  4. Hidden commands: `cmd.hidden = True` is excluded from the help menu entirely.
  5. Narrow width rendering: formatted cleanly without crashing.

- [ ] **Step 2: Run test and verify it fails (RED)**
  Run isolated pytest command.
  Expected: FAIL with `ModuleNotFoundError: No module named 'agent_toolkit_cli._group'`.

- [ ] **Step 3: Implement `AliasedGroup` in `src/agent_toolkit_cli/_group.py`**
  Implement `AliasedGroup` grouping subcommands strictly by `id(cmd)`, canonical name ordering with fallback, sorting aliases, and calling `formatter.write_dl(rows)`.

- [ ] **Step 4: Run test and verify it passes (GREEN)**
  Run isolated pytest command.
  Expected: PASS.

- [ ] **Step 5: Commit Task 1**
  `git add src/agent_toolkit_cli/_group.py tests/test_cli/test_cli_group_aliases_help.py docs/ && git commit -m "feat(cli): add AliasedGroup for collapsing command aliases in help menus"`

---

### Task 2: Apply `AliasedGroup` to aliased asset command groups

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi_extension/__init__.py`
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py`
- Modify: `src/agent_toolkit_cli/commands/agent/__init__.py`
- Modify: `src/agent_toolkit_cli/commands/mcp/__init__.py`
- Modify: `src/agent_toolkit_cli/commands/command/__init__.py`
- Test: `tests/test_cli/test_cli_group_aliases_help.py`

**Interfaces:**
- Consumes: `AliasedGroup` from `agent_toolkit_cli._group`
- Produces: `pi_extension`, `skill`, `agent`, `mcp`, and `command` groups use `AliasedGroup`.

- [ ] **Step 1: Write CLI help integration tests for all asset groups**
  In `tests/test_cli/test_cli_group_aliases_help.py`, add tests asserting:
  1. `agent-toolkit-cli pi-extension --help` shows `list, ls` on one line.
  2. `agent-toolkit-cli skill --help` shows `list, ls` and `remove, rm` on one line each.
  3. `agent-toolkit-cli agent --help`, `mcp --help`, and `command --help` show `list, ls` on one line.
  4. Plural forms (`pi-extensions`, `skills`, `agents`, `mcps`, `commands`) show collapsed aliases.
  5. Unaliased groups (`bundle`, `instructions`) remain unchanged.
  6. Top-level `agent-toolkit-cli --help` displays unchanged canonical plural rows.
  7. Individual alias help (`pi-extension ls --help`, `skill rm --help`) exits 0 and displays command help.
  8. Commands and aliases remain executable.

- [ ] **Step 2: Run tests and verify failure (RED)**
  Run isolated pytest command.
  Expected: FAIL because asset groups still use standard `click.Group`.

- [ ] **Step 3: Update aliased asset groups to use `cls=AliasedGroup`**
  Pass `cls=AliasedGroup` to `@click.group` in `pi_extension`, `skill`, `agent`, `mcp`, `command`.

- [ ] **Step 4: Run tests and verify all pass (GREEN)**
  Run isolated pytest command.
  Expected: PASS.

- [ ] **Step 5: Commit Task 2**
  `git add src/agent_toolkit_cli/ tests/test_cli/test_cli_group_aliases_help.py && git commit -m "fix(cli): use AliasedGroup across aliased asset command groups"`

---

### Task 3: Regression verification across test suite and package build

**Files:**
- Test: `tests/test_cli/test_cli_skill_aliases.py`
- Test: `tests/test_cli/test_command_coverage_guard.py`
- Test: full suite `tests/`
- Build: wheel and sdist package artifacts

- [ ] **Step 1: Run alias and coverage guard regression tests under synthetic isolated HOME**
  Run isolated pytest command for `test_cli_group_aliases_help.py`, `test_cli_skill_aliases.py`, and `test_command_coverage_guard.py`.
  Expected: PASS.

- [ ] **Step 2: Run full test suite under synthetic isolated HOME**
  Verify complete isolation and zero real-user path contamination.
  Expected: PASS.

- [ ] **Step 3: Build package and verify CLI and TUI contents**
  Run `uv build` and inspect wheel contents.
  Expected: SUCCESS.

- [ ] **Step 4: Capture verification evidence**
  Save output artifacts to `assets/verification/516/`.
