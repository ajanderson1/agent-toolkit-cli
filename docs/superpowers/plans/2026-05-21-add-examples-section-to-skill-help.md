# Add `Examples:` section to `skill --help` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a copy-pasteable `Examples:` section to `agent-toolkit-cli skill --help` and a 1–3-line example block to each `skill <subcmd> --help`, so users can crib real invocations instead of assembling them from prose.

**Architecture:** Content-only change via Click's per-command `epilog=` keyword. Each `@click.command(...)` / `@click.group(...)` decorator gets an `epilog=` argument with a multi-line string. Click renders the string verbatim below the Options block. We also add a regression test that asserts the literal `Examples:` heading appears in each affected `--help` invocation, so future refactors can't silently drop it.

**Tech Stack:** Python 3.13, Click, pytest, `click.testing.CliRunner`.

---

## File Structure

**Modified:**

- `src/agent_toolkit_cli/commands/skill/__init__.py` — add `epilog=` to `@click.group()` `skill` and to the four inline `@skill.command(...)` decorators (`add`, `install`, `uninstall`, `remove`).
- `src/agent_toolkit_cli/commands/skill/list_cmd.py` — add `epilog=` to `@click.command("list")`.
- `src/agent_toolkit_cli/commands/skill/status_cmd.py` — add `epilog=` to `@click.command("status")`.
- `src/agent_toolkit_cli/commands/skill/update_cmd.py` — add `epilog=` to `@click.command("update")`.
- `src/agent_toolkit_cli/commands/skill/push_cmd.py` — add `epilog=` to `@click.command("push")`.

**Created:**

- `tests/test_cli_skill_help_examples.py` — pytest module asserting `Examples:` appears in `skill --help` and in each of the eight subcommand `--help` outputs.

Tests for help output already live in `tests/test_cli_help.py` (top-level `--help`); we keep the new tests in a sibling file so the new test surface stays grouped and discoverable.

---

## Task 1: Regression tests — assert `Examples:` literal in every targeted `--help`

Write the failing tests first so we know the epilogs are landing where we expect.

**Files:**
- Create: `tests/test_cli_skill_help_examples.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Each `skill --help` and `skill <subcmd> --help` ends with an Examples: section."""
import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _help(args: list[str]) -> str:
    runner = CliRunner()
    result = runner.invoke(main, args)
    assert result.exit_code == 0, result.output
    return result.output


def test_skill_group_help_has_examples_section():
    out = _help(["skill", "--help"])
    assert "Examples:" in out, out


@pytest.mark.parametrize(
    "subcmd",
    ["add", "install", "uninstall", "list", "status", "update", "push", "remove"],
)
def test_skill_subcommand_help_has_examples_section(subcmd: str):
    out = _help(["skill", subcmd, "--help"])
    assert "Examples:" in out, out


def test_skill_help_no_deprecated_commands_in_examples():
    """The Examples block must only reference v2 commands."""
    out = _help(["skill", "--help"])
    # Carve out the Examples section (everything after the literal heading).
    examples = out.split("Examples:", 1)[1]
    for removed in ("check ", "link ", "doctor ", "fix ", "ingest ",
                    "inventory ", "migrate-skills ", "diff ", "unlink ", " pi "):
        assert removed not in examples, (
            f"deprecated token {removed!r} appears in Examples block"
        )
    assert "--harness" not in examples, "--harness is a pre-v2 flag"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_skill_help_examples.py -v`
Expected: 10 FAILs (1 group test + 8 subcommand tests + 1 deprecated-token guard), each because `assert "Examples:" in out` fails on the current help output.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_cli_skill_help_examples.py
git commit -m "test(cli): assert Examples: section in skill --help and subcommands"
```

---

## Task 2: Add the top-level `Examples:` epilog to the `skill` group

Wire the long `Examples:` block from the spec into `@click.group()`.

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py:37-39`

- [ ] **Step 1: Replace the bare `@click.group()` with one that carries `epilog=`**

Current code (lines 37–39):

```python
@click.group()
def skill() -> None:
    """Manage skills via per-skill upstream git repos + skills-lock.json."""
```

New code — paste verbatim, including the trailing blank line inside the triple-quoted string:

```python
_SKILL_GROUP_EPILOG = """\
Examples:
  # Add a skill to the global library (clone only — no symlinks yet)
  $ agent-toolkit-cli skill add anthropics/skills

  # Pin to a branch or tag
  $ agent-toolkit-cli skill add anthropics/skills --ref main
  $ agent-toolkit-cli skill add anthropics/skills --ref v1.2.0

  # Override the local slug
  $ agent-toolkit-cli skill add ajanderson1/journal-skill --slug journal

  # Make it visible to a specific agent (claude-code) or all universal agents
  $ agent-toolkit-cli skill install journal --agents claude-code
  $ agent-toolkit-cli skill install journal --agents universal
  $ agent-toolkit-cli skill install journal --agents all

  # Project-scope install (canonical lives under <project>/.agents/skills/)
  $ agent-toolkit-cli skill install journal --agents claude-code -p

  # List, status, update, push
  $ agent-toolkit-cli skill list                       # global by default
  $ agent-toolkit-cli skill list -p                    # project scope
  $ agent-toolkit-cli skill status                     # show clean/dirty/missing per skill
  $ agent-toolkit-cli skill update                     # fetch + merge upstream for all
  $ agent-toolkit-cli skill update journal             # one skill only
  $ agent-toolkit-cli skill push journal               # self-improvements upstream

  # Take down agent visibility but keep the canonical clone
  $ agent-toolkit-cli skill uninstall journal --agents claude-code

  # Remove a skill completely (interactive picker if no slug given)
  $ agent-toolkit-cli skill remove journal
  $ agent-toolkit-cli skill remove                     # interactive
  $ agent-toolkit-cli skill remove journal --force     # discard dirty changes
"""


@click.group(epilog=_SKILL_GROUP_EPILOG)
def skill() -> None:
    """Manage skills via per-skill upstream git repos + skills-lock.json."""
```

Place the `_SKILL_GROUP_EPILOG` constant **directly above** the `@click.group(...)` decorator (i.e., just before line 37). Imports at the top of the file already include `click`; no new imports are needed.

- [ ] **Step 2: Run the group test to verify it passes**

Run: `uv run pytest tests/test_cli_skill_help_examples.py::test_skill_group_help_has_examples_section -v`
Expected: PASS.

- [ ] **Step 3: Manual visual check**

Run: `uv run agent-toolkit-cli skill --help`
Expected: the existing usage/options block, then a blank line, then the `Examples:` block, with the `$` lines indented two spaces under each comment.

- [ ] **Step 4: Run the deprecated-token guard**

Run: `uv run pytest tests/test_cli_skill_help_examples.py::test_skill_help_no_deprecated_commands_in_examples -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/__init__.py
git commit -m "docs(cli): add Examples: block to skill --help group epilog"
```

---

## Task 3: Add per-subcommand `Examples:` epilogs (inline commands: add, install, uninstall, remove)

Four commands are defined inline in `__init__.py`. Add `epilog=` to each.

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py` (decorators only)

- [ ] **Step 1: `add` — replace decorator line 59 with `epilog=`**

Current:

```python
@skill.command("add")
@click.argument("source", required=True)
```

New (only the `@skill.command(...)` line changes; the `@click.argument(...)` line below it stays exactly as-is):

```python
@skill.command("add", epilog="""\
Examples:
  agent-toolkit-cli skill add anthropics/skills
  agent-toolkit-cli skill add anthropics/skills --ref v1.2.0
  agent-toolkit-cli skill add ajanderson1/journal-skill --slug journal
""")
@click.argument("source", required=True)
```

- [ ] **Step 2: `install` — replace decorator line 132**

Current:

```python
@skill.command("install")
@click.argument("slug", required=True)
```

New:

```python
@skill.command("install", epilog="""\
Examples:
  agent-toolkit-cli skill install journal --agents claude-code
  agent-toolkit-cli skill install journal --agents universal
  agent-toolkit-cli skill install journal --agents claude-code -p
""")
@click.argument("slug", required=True)
```

- [ ] **Step 3: `uninstall` — replace decorator line 230**

Current:

```python
@skill.command("uninstall")
@click.argument("slug", required=True)
```

New:

```python
@skill.command("uninstall", epilog="""\
Examples:
  agent-toolkit-cli skill uninstall journal --agents claude-code
  agent-toolkit-cli skill uninstall journal --agents all
""")
@click.argument("slug", required=True)
```

- [ ] **Step 4: `remove` — replace decorator line 290**

Current:

```python
@skill.command("remove")
@click.argument("slugs", nargs=-1, required=False)
```

New:

```python
@skill.command("remove", epilog="""\
Examples:
  agent-toolkit-cli skill remove journal
  agent-toolkit-cli skill remove                   # interactive picker
  agent-toolkit-cli skill remove journal --force   # discard dirty changes
""")
@click.argument("slugs", nargs=-1, required=False)
```

> **Note for the executor:** line numbers reflect HEAD at plan-write time and may shift by 1–2 after Task 2 inserts the `_SKILL_GROUP_EPILOG` constant. Match by decorator content, not line number, if they don't line up.

- [ ] **Step 5: Run the four matching tests**

Run:
```bash
uv run pytest tests/test_cli_skill_help_examples.py -k "add or install or uninstall or remove" -v
```
Expected: 4 PASSes.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/__init__.py
git commit -m "docs(cli): add Examples: epilog to skill add/install/uninstall/remove"
```

---

## Task 4: Add per-subcommand `Examples:` epilogs (separate-file commands: list, status, update, push)

Four more commands live in their own files. Same pattern: replace the bare `@click.command("<name>")` with `@click.command("<name>", epilog="""...""")`.

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/list_cmd.py:12`
- Modify: `src/agent_toolkit_cli/commands/skill/status_cmd.py:13`
- Modify: `src/agent_toolkit_cli/commands/skill/update_cmd.py:13`
- Modify: `src/agent_toolkit_cli/commands/skill/push_cmd.py:15`

- [ ] **Step 1: `list_cmd.py` — replace line 12**

Current line 12: `@click.command("list")`

New (lines 12–17 become):

```python
@click.command("list", epilog="""\
Examples:
  agent-toolkit-cli skill list        # global skills
  agent-toolkit-cli skill list -p     # project-scope skills
""")
```

- [ ] **Step 2: `status_cmd.py` — replace line 13**

Current line 13: `@click.command("status")`

New:

```python
@click.command("status", epilog="""\
Examples:
  agent-toolkit-cli skill status              # all skills
  agent-toolkit-cli skill status journal      # one skill
""")
```

- [ ] **Step 3: `update_cmd.py` — replace line 13**

Current line 13: `@click.command("update")`

New:

```python
@click.command("update", epilog="""\
Examples:
  agent-toolkit-cli skill update              # update all skills
  agent-toolkit-cli skill update journal      # update one skill
""")
```

- [ ] **Step 4: `push_cmd.py` — replace line 15**

Current line 15: `@click.command("push")`

New:

```python
@click.command("push", epilog="""\
Examples:
  agent-toolkit-cli skill push                # push all dirty skills
  agent-toolkit-cli skill push journal        # push one skill
""")
```

- [ ] **Step 5: Run the four matching tests**

Run:
```bash
uv run pytest tests/test_cli_skill_help_examples.py -k "list or status or update or push" -v
```
Expected: 4 PASSes.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/list_cmd.py \
        src/agent_toolkit_cli/commands/skill/status_cmd.py \
        src/agent_toolkit_cli/commands/skill/update_cmd.py \
        src/agent_toolkit_cli/commands/skill/push_cmd.py
git commit -m "docs(cli): add Examples: epilog to skill list/status/update/push"
```

---

## Task 5: Final verification — full test suite + manual eyeball

Make sure nothing else broke, and capture a help-output sample for the PR artifacts.

**Files:** (none changed in this task)

- [ ] **Step 1: Full test suite**

Run: `uv run pytest -q`
Expected: all passing (baseline before this work was 144 passed, 2 skipped). Should now be 154 passed, 2 skipped (or similar — 1 group test + 8 subcommand tests + 1 deprecated-token guard added).

- [ ] **Step 2: Capture top-level help to the verification dir**

Run:
```bash
uv run agent-toolkit-cli skill --help > assets/verification/168/skill-help-after.txt 2>&1
```

Expected: the file contains both the existing `Usage:` / `Options:` / `Commands:` blocks AND the new `Examples:` block.

- [ ] **Step 3: Capture each subcommand help**

Run:
```bash
for cmd in add install uninstall list status update push remove; do
  echo "=== skill $cmd --help ==="
  uv run agent-toolkit-cli skill "$cmd" --help
  echo
done > assets/verification/168/skill-subcmd-help-after.txt 2>&1
```

Expected: each block ends with `Examples:` followed by 1–3 example lines.

- [ ] **Step 4: Eyeball the captures**

Read both files. Confirm:
- `Examples:` literal appears once per `--help` (8 subcommands + 1 group = 9 occurrences).
- Indentation is consistent (no tabs, two-space indent under each comment).
- No deprecated commands or flags appear.

- [ ] **Step 5: No commit needed — artifacts are gitignored**

`assets/verification/` is in `.gitignore` (verified at flow Step 9 setup). These captures stay local for the PR body to reference.

---

## Self-Review (executed by the planner, recorded here)

**1. Spec coverage:**
- DoD bullet "top-level `skill --help` ends with the `Examples:` block" → Task 2 ✓
- DoD bullet "each subcommand `--help` includes an `Examples:` block with ≥1 example" → Tasks 3 + 4 ✓
- DoD bullet "only v2 commands and flags" → guarded by `test_skill_help_no_deprecated_commands_in_examples` in Task 1 ✓
- DoD bullet "no flag/command/section changes" → enforced implicitly: only decorator kwargs change ✓
- DoD bullet "`uv run pytest -q` green" → Task 5 Step 1 ✓
- DoD bullet "new test pins the Examples section" → Task 1 ✓

**2. Placeholder scan:** No `TBD`, `TODO`, "implement later", or "similar to Task N". Every code block is paste-ready.

**3. Type consistency:** No new types or method signatures introduced. The only new symbol is the module-level constant `_SKILL_GROUP_EPILOG` in `__init__.py`, used once on the next line.

**Possible-friction note for the executor:** Click renders `epilog` text with leading/trailing whitespace stripped per-paragraph; the `"""\` opening avoids a stray blank line at the top of the rendered block. If the rendered output looks wrong, double-check that the triple-quoted string starts with a backslash-continuation and **not** a blank line.
