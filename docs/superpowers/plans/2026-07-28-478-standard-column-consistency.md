# Standard Column Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One shared rule owns the Standard column header (`Standard (N)`, first position) for every asset type that has a standard slot; asset types without one are a documented, tested exception; the Commands grid stops advertising a slot it does not have.

**Architecture:** Add `standard_column_header(asset_type, scope) -> str | None` to `agent_toolkit_tui/display_names.py`, backed by a per-asset-type count resolver that reads each existing SSOT at call time. Replace the four copy-pasted `if harness == "standard": standard_label(...)` branches with calls to it. Fix the Commands grid's labels and docstrings. Add a rule-level invariant test.

**Scope guard — read first:** this is **display consistency only**. Commands does not get a real Standard column here; that needs a new convergence projection (adapter, per-scope reader SSOT, install fan-out, lockfile entries) and is issue **#482**. If a step tempts you into `command_adapters/`, stop — you have left this issue.

**Tech Stack:** Python 3.13-compatible, Textual `DataTable`, pytest + pytest-asyncio, existing `agent_toolkit_tui` patterns.

**Spec:** `docs/superpowers/specs/2026-07-28-478-standard-column-consistency.md`

---

## Implementation Units

- Modify `src/agent_toolkit_tui/display_names.py`: add `standard_column_header()` and its count resolver.
- Modify `src/agent_toolkit_tui/widgets/skill_grid.py`, `instruction_grid.py`, `agent_grid.py`, `mcp_grid.py`: call the shared helper.
- Modify `src/agent_toolkit_tui/widgets/command_grid.py`: `harness_label()` headers; correct docstrings; annotate the dormant `"standard"` branch.
- Create `tests/test_tui/test_standard_column_rule.py`: the rule-level invariant.
- Modify `tests/test_tui/test_display_names.py` and `tests/test_tui/test_command_grid.py`.

## Task 1: Lock the current behaviour, then write the rule test

**Files:**
- Create: `tests/test_tui/test_standard_column_rule.py`
- Read for idiom: `tests/test_tui/test_composition.py`, `tests/test_tui/test_agent_grid_standard.py`, `tests/test_tui/test_display_names.py`

- [ ] **Step 1: Write the rule-level invariant test**

Create `tests/test_tui/test_standard_column_rule.py`:

```python
"""The Standard-column rule (#478).

Rule: for every asset type that HAS a standard slot at a given scope, the
first column after the slug column is headed `Standard (N)` with the live
covered count. Asset types with no standard slot are listed explicitly below,
with the reason — so a new asset type cannot drift in silently.
"""
from __future__ import annotations

import re

import pytest

from agent_toolkit_tui.display_names import standard_column_header

STANDARD_RE = re.compile(r"^Standard \(\d+\)$")

# (asset_type, scope) -> reason there is no standard slot. Spec R4/R5.
NO_STANDARD_SLOT = {
    ("pi-extension", "global"): "single-harness asset type; no convergence dir",
    ("pi-extension", "project"): "single-harness asset type; no convergence dir",
    ("mcp", "global"): "the standard projection IS the project .mcp.json",
    ("command", "global"): "no standard projection yet — see #482",
    ("command", "project"): "no standard projection yet — see #482",
}

ASSET_TYPES = ["instruction", "command", "skill", "agent", "mcp", "pi-extension"]


@pytest.mark.parametrize("asset_type", ASSET_TYPES)
@pytest.mark.parametrize("scope", ["global", "project"])
def test_standard_header_rule(asset_type: str, scope: str):
    header = standard_column_header(asset_type, scope)
    if (asset_type, scope) in NO_STANDARD_SLOT:
        assert header is None, (
            f"{asset_type}/{scope} is on the no-standard-slot exception list "
            f"({NO_STANDARD_SLOT[(asset_type, scope)]}) but returned {header!r}. "
            "If it gained a standard slot, remove it from the list."
        )
        return
    assert header is not None, f"{asset_type}/{scope} has no standard header"
    assert STANDARD_RE.match(header), f"{asset_type}/{scope} header was {header!r}"


def test_unknown_asset_type_is_loud():
    """Fail loudly: an unregistered asset type is a bug, not a None."""
    with pytest.raises(KeyError):
        standard_column_header("nonsense", "global")


def test_agents_count_differs_by_scope():
    """devin reads .claude/agents at project scope only, so the count moves.
    A stale header is a live defect, not a hypothetical (spec R3)."""
    assert standard_column_header("agent", "global") != standard_column_header(
        "agent", "project"
    )
```

- [ ] **Step 2: Run and confirm it fails for the right reason**

```bash
uv run pytest tests/test_tui/test_standard_column_rule.py -q
```

Expected: collection-time `ImportError` — `standard_column_header` does not exist yet. That is the correct red.

- [ ] **Step 3: Confirm the scope-asymmetry premise before building on it**

```bash
uv run python -c "from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered as c; print(len(c('global')), len(c('project')))"
```

Expected: two different numbers (`5` and `6` at time of writing — `devin` is project-only). If they are equal, `test_agents_count_differs_by_scope` is wrong: delete it and record why in the PR body rather than weakening the rule test.

## Task 2: Build the shared header helper

**Files:**
- Modify: `src/agent_toolkit_tui/display_names.py`
- Modify: `tests/test_tui/test_display_names.py`

- [ ] **Step 1: Add the count resolver and the header helper**

Append to `src/agent_toolkit_tui/display_names.py`:

```python
def _standard_covered_count(asset_type: str, scope: str) -> int | None:
    """Live covered-harness count for `asset_type` at `scope`.

    None means "this asset type has no standard slot here" (#478 R4/R5), which
    is a real answer — not an error. An UNKNOWN asset type raises KeyError, so
    a new asset type cannot be silently treated as slot-less.

    Imports are function-local and resolved at call time on purpose: the counts
    must track the SSOT, never an import-time snapshot (#478 R1).
    """
    if asset_type not in _ASSET_TYPE_SINGULAR:
        raise KeyError(f"unknown asset type: {asset_type!r}")

    if asset_type == "skill":
        from agent_toolkit_cli.skill_agents import get_standard_agents

        return len(get_standard_agents())

    if asset_type == "agent":
        from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered

        return len(agents_standard_covered(scope))

    if asset_type == "instruction":
        from agent_toolkit_cli.instructions_matrix import instructions_matrix_rows

        return sum(1 for row in instructions_matrix_rows() if row["verdict"] == "native")

    if asset_type == "mcp":
        from agent_toolkit_cli.mcp_standard import mcp_standard_covered

        try:
            return len(mcp_standard_covered(scope))
        except KeyError:
            # Deliberate: STANDARD_MCP_READERS has only a 'project' key. The
            # standard MCP projection IS the project .mcp.json, so there is no
            # global slot to count (#478 R4, composition.py:58-71).
            return None

    # command: no standard projection exists yet (#482).
    # pi-extension: single-harness asset type; nothing converges (#478 R5).
    return None


def standard_column_header(asset_type: str, scope: str) -> str | None:
    """`Standard (N)` for the standard column, or None if there is no slot.

    Single owner of the standard-column header rule (#478 R1). Every grid calls
    this instead of re-deriving the count behind its own special case.
    """
    count = _standard_covered_count(asset_type, scope)
    if count is None:
        return None
    return standard_label(count)
```

- [ ] **Step 2: Verify the helper against the rule test**

```bash
uv run pytest tests/test_tui/test_standard_column_rule.py tests/test_tui/test_display_names.py -q
```

Expected: PASS. If `instructions_matrix_rows` or `mcp_standard` import paths differ, fix the import — do not inline a literal count.

- [ ] **Step 3: Commit the helper**

```bash
git add src/agent_toolkit_tui/display_names.py tests/test_tui/test_standard_column_rule.py
git commit -m "feat(tui): single owner for the Standard column header"
```

Include the `Device:` trailer.

## Task 3: Route the four grids through the helper

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py`
- Modify: `src/agent_toolkit_tui/widgets/instruction_grid.py`
- Modify: `src/agent_toolkit_tui/widgets/agent_grid.py`
- Modify: `src/agent_toolkit_tui/widgets/mcp_grid.py`

- [ ] **Step 1: Skills**

In `_rebuild` (`skill_grid.py:591-593`), replace:

```python
            base = standard_label(len(get_standard_agents())) if agent == "standard" else harness_label(agent)
```

with:

```python
            base = (
                standard_column_header("skill", self._scope) or standard_label(0)
                if agent == "standard"
                else harness_label(agent)
            )
```

Prefer the clearer explicit form if the ternary nests awkwardly:

```python
            if agent == "standard":
                base = standard_column_header("skill", self._scope)
                assert base is not None, "skills always have a standard slot"
            else:
                base = harness_label(agent)
```

Update the import line to bring in `standard_column_header`. Drop the now-unused
`get_standard_agents` import **only if** nothing else in the file uses it —
check with `rg -n "get_standard_agents" src/agent_toolkit_tui/widgets/skill_grid.py`.

- [ ] **Step 2: Agents**

In `agent_grid.py:423-429`, replace the inline
`standard_label(len(agents_standard_covered(self._scope)))` block with
`standard_column_header("agent", self._scope)`, and remove the function-local
`from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered`
import **from that call site only** — `_context_for` (`agent_grid.py:372-377`)
still needs it to enumerate names for the info panel. Do not remove that one.

- [ ] **Step 3: MCPs**

In `mcp_grid.py:429-435`, replace the `if harness == "standard":` block with
`standard_column_header("mcp", self._scope)`. The helper returns `None` at
global scope, but `self._harnesses()` already omits `"standard"` there, so the
branch is unreachable at global scope — assert rather than silently fall back:

```python
            if harness == "standard":
                base = standard_column_header("mcp", self._scope)
                assert base is not None, (
                    "mcp grid rendered a standard column at a scope with no "
                    "standard slot — _harnesses() and the header rule disagree"
                )
```

- [ ] **Step 4: Instructions**

In `instruction_grid.py:480-482`, replace `standard_label(_standard_count())`
with `standard_column_header("instruction", self._scope)`. Delete the now-dead
module-level `_standard_count()` (`instruction_grid.py:69-72`) — its logic moved
into the resolver. Confirm nothing else calls it:

```bash
rg -n "_standard_count" src/ tests/
```

- [ ] **Step 5: Run the grid suites**

```bash
uv run pytest tests/test_tui -q
```

Expected: PASS. `test_agent_grid_standard.py`, `test_skill_grid_new_columns.py`,
`test_instruction_grid_groups.py`, and `test_mcp_grid.py` assert header text —
if one fails on exact text, the *header* is the thing under test; confirm the
new text is identical to the old before editing any assertion.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui/widgets tests/test_tui
git commit -m "refactor(tui): grids share the Standard column header rule"
```

## Task 4: Stop the Commands grid lying

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/command_grid.py`
- Modify: `tests/test_tui/test_command_grid.py`

- [ ] **Step 1: Write the failing label test**

Add to `tests/test_tui/test_command_grid.py`:

```python
@pytest.mark.asyncio
async def test_command_headers_use_display_labels():
    """#448 sweep escapee: headers rendered raw catalog keys (#478 R6)."""
    app = CommandGridApp()  # reuse the module's existing harness app
    async with app.run_test() as pilot:
        table = app.query_one("#command-table", DataTable)
        headers = [str(c.label) for c in table.columns.values()]
        assert any(h.startswith("Claude") for h in headers), headers
        assert any(h.startswith("Gemini") for h in headers), headers
        assert not any(h.startswith("claude-code") for h in headers), headers
        assert not any(h.startswith("gemini-cli") for h in headers), headers
```

If the module has no reusable app harness, copy the smallest one from
`tests/test_tui/test_asset_grid_filters.py`.

```bash
uv run pytest tests/test_tui/test_command_grid.py -q
```

Expected: the new test FAILS.

- [ ] **Step 2: Use display labels**

In `command_grid.py:404-405`, replace:

```python
        for harness in INTERACTIVE_HARNESSES:
            table.add_column(f"{harness} {_INFO_GLYPH}", width=_HARNESS_COL_WIDTH)
```

with:

```python
        # Display labels, not raw catalog keys (#478 R6 — escapee from the
        # #448 terminology sweep). There is no Standard column here: commands
        # have no convergence projection yet (#482).
        for harness in INTERACTIVE_HARNESSES:
            table.add_column(f"{harness_label(harness)} {_INFO_GLYPH}", width=_HARNESS_COL_WIDTH)
```

Add `harness_label` to the imports from `agent_toolkit_tui.display_names`.

Check `_HARNESS_COL_WIDTH` still fits the longest label (`OpenCode` is 8 chars;
`Gemini` 6) — if a label truncates, widen the constant here rather than
reverting to raw keys.

- [ ] **Step 3: Correct the docstrings**

Replace the module docstring's first line (`command_grid.py:3`):

```python
Columns: COMMAND ⓘ | Claude ⓘ | Pi ⓘ | Gemini ⓘ | State | Source.

There is NO Standard column: unlike skills (#351), agents (#361) and MCPs
(#399), the commands asset type has no convergence projection yet — see #482.
The `"standard"` branches below are dormant until it lands.
```

Replace the inline comment at `command_grid.py:400-403` with a one-line pointer
to #482, and correct `_context_for`'s docstring so it no longer claims to
enumerate `.claude/commands` readers from a per-scope SSOT that does not exist.

Annotate the dormant branch in `_column_key_for_index`:

```python
        # Dormant until #482 adds a commands standard projection:
        # INTERACTIVE_HARNESSES (= DEFAULT_HARNESSES) never contains "standard"
        # today, so this branch is unreachable. Kept deliberately so the column
        # wiring is already correct when the projection lands.
        if self._harness_for_column(col) == "standard":
            return "standard"
```

- [ ] **Step 4: Verify**

```bash
uv run pytest tests/test_tui/test_command_grid.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/command_grid.py tests/test_tui/test_command_grid.py
git commit -m "fix(tui): command headers use display labels, not catalog keys"
```

## Task 5: Regression sweep and visual check

- [ ] **Step 1: Full suite**

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 2: Scan for surviving copies of the rule**

```bash
rg -n "standard_label\(" src/agent_toolkit_tui
```

Expected: `standard_label` is called **only** from `standard_column_header` in
`display_names.py`. Any remaining grid-side call is a missed migration.

```bash
rg -n 'harness == "standard"' src/agent_toolkit_tui
```

Expected: only info-panel/context branches and the annotated dormant Commands
branch — no header-building branches.

- [ ] **Step 3: Manual visual check**

```bash
uv run agent-toolkit-tui
```

Checks, at **both** scopes (`ctrl+g`):

1. Skills, Instructions, Agents: first column after the slug reads
   `Standard (N) ⓘ`.
2. MCPs: `Standard (2) ⓘ` at project scope; no Standard column at global.
3. Agents: the `(N)` **changes** across the scope toggle.
4. Commands: headers read `Claude`, `Pi`, `Gemini`; no Standard column.
5. Pi Extensions: `Pi` column, unchanged.
6. No header is truncated mid-word by the width constants.

Capture a screenshot per asset type into `assets/verification/issue-478/` and
write a one-line visual verdict in the PR body, per
`~/.conventions/conventions/testing.md`.

- [ ] **Step 4: Final commit if the sweep changed anything**

```bash
git add src/agent_toolkit_tui tests/test_tui
git commit -m "test(tui): guard the Standard column rule"
```

## Risk controls

- **Do not touch `src/agent_toolkit_cli/command_adapters/`.** A Commands
  standard projection is #482. If you find yourself adding a reader set, stop.
- Do not hardcode any count. Every count resolves from an SSOT at call time.
- Do not silence `mcp_standard_covered("global")`'s `KeyError` anywhere except
  the one documented site in `_standard_covered_count`; it is deliberate
  fail-loud design.
- Do not "fix" `agent_state.INTERACTIVE_HARNESSES`'s import-time
  `agents_nonstandard_main("global")` snapshot — out of scope, noted in the spec.
- Do not change column widths beyond what a display label demands, and do not
  touch truncation behaviour (#459).
- If an existing test asserts a header string that must change, treat that as a
  behaviour question and confirm the new string first — those tests are the
  regression net for exactly this rule.

## Self-review checklist

- Spec coverage: R1 Task 2; R2 Task 1 Step 1 + Task 3; R3
  `test_agents_count_differs_by_scope` + manual check 3; R4 Task 2 Step 1 MCP
  branch + Task 3 Step 3; R5 the `NO_STANDARD_SLOT` list; R6 Task 4; R7 Task 1
  and Task 5 Step 2.
- Test-first: Tasks 1 and 4 land failing tests before implementation.
- Scope guard: no file under `src/agent_toolkit_cli/` is modified.
- Placeholder scan: no `TODO(...)` or `<...>` remains in any step.
