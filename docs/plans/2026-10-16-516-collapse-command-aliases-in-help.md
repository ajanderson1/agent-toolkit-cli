Issue: #516
# Collapse Command Aliases into Single Entries in Group Help Menus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Present aliased subcommands sharing a callback as a single combined entry (e.g. `list, ls` and `remove, rm`) in Click group help menus across all toolkit asset kinds.
**Architecture:** Create an `AliasedGroup(click.Group)` in `src/agent_toolkit_cli/_group.py` that groups subcommands sharing a callback into combined entries (`canonical, alias1, ...`) and calculates proper column spacing. Apply `AliasedGroup` to all asset command groups in `agent_toolkit_cli`.
**Tech Stack:** Python 3.9+, Click, pytest.
**Spec:** `docs/specs/2026-10-16-516-collapse-command-aliases-in-help.md`

## Global Constraints
- Python 3.9+ compatibility.
- Do not remove or rename any existing command or alias; dispatch and execution behavior must remain identical.
- Canonical command name must appear first in combined help entries.
- Column indentation and alignment in Click help output must be preserved.
- All existing tests including coverage guards must pass cleanly.

## Review Focus
- Trailing or missing spacing in help formatting when aliases vary in length.
- Groups without aliases (e.g., `bundle`, `instructions`) formatting identically to standard Click groups.
- Hidden subcommands (`cmd.hidden = True`) remaining hidden and not appearing as aliases.
- Individual alias `--help` invocation (e.g., `agent-toolkit-cli pi-extension ls --help`) continuing to work.
- Plural group aliases (`skills`, `agents`, `commands`, `mcps`, `pi-extensions`) properly inheriting `AliasedGroup` formatting.

---

### Task 1: Create `AliasedGroup` class with tests

**Files:**
- Create: `src/agent_toolkit_cli/_group.py`
- Test: `tests/test_cli/test_cli_group_aliases_help.py`

**Interfaces:**
- Consumes: `click.Group`, `click.Context`, `click.HelpFormatter`
- Produces: `AliasedGroup` subclass of `click.Group` with overridden `format_commands(ctx, formatter)`

- [ ] **Step 1: Write failing unit test for `AliasedGroup`**
  In `tests/test_cli/test_cli_group_aliases_help.py`, define a test with a dummy `AliasedGroup` having commands `list` and `ls` sharing a callback, and assert that `--help` displays `list, ls` on one row and no standalone `ls` row.

- [ ] **Step 2: Run test and verify it fails**
  Run: `uv run pytest -q tests/test_cli/test_cli_group_aliases_help.py`
  Expected: FAIL with `ModuleNotFoundError: No module named 'agent_toolkit_cli._group'`.

- [ ] **Step 3: Implement `AliasedGroup` in `src/agent_toolkit_cli/_group.py`**
  Implement `AliasedGroup` grouping subcommands by callback/id, ordering canonical first, sorting aliases, and calling `formatter.write_dl(rows)`.

- [ ] **Step 4: Run test and verify it passes**
  Run: `uv run pytest -q tests/test_cli/test_cli_group_aliases_help.py`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git add src/agent_toolkit_cli/_group.py tests/test_cli/test_cli_group_aliases_help.py && git commit -m "feat(cli): add AliasedGroup for collapsing command aliases in help menus"`

---

### Task 2: Apply `AliasedGroup` to all asset command groups

**Files:**
- Modify: `src/agent_toolkit_cli/cli.py`
- Modify: `src/agent_toolkit_cli/commands/pi_extension/__init__.py`
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py`
- Modify: `src/agent_toolkit_cli/commands/agent/__init__.py`
- Modify: `src/agent_toolkit_cli/commands/mcp/__init__.py`
- Modify: `src/agent_toolkit_cli/commands/command/__init__.py`
- Modify: `src/agent_toolkit_cli/commands/bundle/__init__.py`
- Modify: `src/agent_toolkit_cli/commands/instructions/__init__.py`
- Test: `tests/test_cli/test_cli_group_aliases_help.py`

**Interfaces:**
- Consumes: `AliasedGroup` from `agent_toolkit_cli._group`
- Produces: All CLI asset command groups use `AliasedGroup` as their group class.

- [ ] **Step 1: Write comprehensive CLI help tests for all asset groups**
  In `tests/test_cli/test_cli_group_aliases_help.py`, add tests invoking `main` with `--help` for `pi-extension`, `skill`, `agent`, `mcp`, `command`, and their plural aliases, asserting `list, ls` (and `remove, rm` for `skill`) appear on single rows and standalone `ls` / `rm` do not appear.

- [ ] **Step 2: Run tests and verify failure**
  Run: `uv run pytest -q tests/test_cli/test_cli_group_aliases_help.py`
  Expected: FAIL because asset groups still use default `click.Group`.

- [ ] **Step 3: Update all asset command groups to use `cls=AliasedGroup`**
  Update `AssetCommandGroup(AliasedGroup)` in `cli.py`, and pass `cls=AliasedGroup` to `@click.group` in `pi_extension`, `skill`, `agent`, `mcp`, `command`, `bundle`, `instructions`.

- [ ] **Step 4: Run tests and verify all pass**
  Run: `uv run pytest -q tests/test_cli/test_cli_group_aliases_help.py`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git add src/agent_toolkit_cli/ tests/test_cli/test_cli_group_aliases_help.py && git commit -m "fix(cli): use AliasedGroup across all asset command groups"`

---

### Task 3: Regression verification across test suite

**Files:**
- Test: `tests/test_cli/test_cli_skill_aliases.py`
- Test: `tests/test_cli/test_command_coverage_guard.py`
- Test: full suite `tests/`

- [ ] **Step 1: Run alias and coverage guard regression tests**
  Run: `uv run pytest -q tests/test_cli/test_cli_skill_aliases.py tests/test_cli/test_command_coverage_guard.py`
  Expected: PASS.

- [ ] **Step 2: Run full test suite**
  Run: `uv run pytest -q`
  Expected: PASS.

- [ ] **Step 3: Verification smoke on real CLI outputs**
  Run: `uv run agent-toolkit-cli pi-extension --help`
  Run: `uv run agent-toolkit-cli skill --help`
  Confirm visual alignment and collapsed rows.
