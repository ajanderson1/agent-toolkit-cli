# All Asset Pane Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Skills-style filter boxes to every Textual TUI asset pane and route `/` to the active pane's filter.

**Architecture:** Extract the Down/Tab focus handoff into a tiny shared `GridFilterInput`, then add per-grid filter state and visible-row mapping to each non-skill grid. Keep bulk actions and app status math on each grid's full `_rows` collection.

**Tech Stack:** Python 3.13-compatible code, Textual `Input`/`DataTable`, pytest async TUI tests, existing `agent_toolkit_tui` widget patterns.

---

## Implementation Units

- Create `src/agent_toolkit_tui/widgets/filter_input.py`: shared filter input with table-focus handoff.
- Modify `src/agent_toolkit_tui/widgets/skill_grid.py`: use shared input without changing behavior.
- Modify `src/agent_toolkit_tui/widgets/instruction_grid.py`: add `#instruction-filter` and visible-row action mapping.
- Modify `src/agent_toolkit_tui/widgets/command_grid.py`: add `#command-filter` and visible-row action mapping.
- Modify `src/agent_toolkit_tui/widgets/pi_grid.py`: add `#pi-filter` and visible-row action mapping.
- Modify `src/agent_toolkit_tui/widgets/agent_grid.py`: add `#agent-filter` and visible-row action mapping.
- Modify `src/agent_toolkit_tui/widgets/mcp_grid.py`: add `#mcp-filter` and visible-row action mapping.
- Modify `src/agent_toolkit_tui/app.py`: route `/` to the active pane filter.
- Add/extend tests under `tests/test_tui/` for non-skill filters and app focus routing.

## Task 1: Extract reusable filter input

**Files:**
- Create: `src/agent_toolkit_tui/widgets/filter_input.py`
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py`
- Test: `tests/test_tui/test_skill_grid_filter.py`

- [ ] **Step 1: Write shared input module**

Create `src/agent_toolkit_tui/widgets/filter_input.py`:

```python
"""Shared TUI filter input for asset grids."""
from __future__ import annotations

from textual import events
from textual.css.query import NoMatches
from textual.widgets import DataTable, Input


class GridFilterInput(Input):
    """Filter box that hands focus to its sibling table on Down / Tab."""

    def __init__(
        self,
        *,
        table_selector: str,
        placeholder: str = "filter…",
        id: str | None = None,
    ) -> None:
        super().__init__(placeholder=placeholder, id=id)
        self.table_selector = table_selector

    def on_key(self, event: events.Key) -> None:
        if event.key in ("down", "tab"):
            try:
                self.screen.query_one(self.table_selector, DataTable).focus()
            except NoMatches:
                return
            event.stop()
            event.prevent_default()
```

- [ ] **Step 2: Switch Skills grid to shared input**

In `src/agent_toolkit_tui/widgets/skill_grid.py`, replace local `FilterInput` with the shared widget.

Remove these imports if they become unused:

```python
from textual import events
from textual.css.query import NoMatches
```

Add:

```python
from agent_toolkit_tui.widgets.filter_input import GridFilterInput
```

Delete the local `FilterInput` class. In `compose()`, replace the first yield with:

```python
yield GridFilterInput(table_selector="#skill-table", id="skill-filter")
```

Keep `from textual.widgets import DataTable, Input` because `Input.Changed` and `Input.Submitted` handlers still use `Input`.

- [ ] **Step 3: Verify Skills behavior is unchanged**

Run:

```bash
uv run pytest tests/test_tui/test_skill_grid_filter.py -q
```

Expected: PASS. If Down/Tab or typing tests fail, restore the local class behavior exactly inside `GridFilterInput` before continuing.

- [ ] **Step 4: Commit shared input extraction**

```bash
git add src/agent_toolkit_tui/widgets/filter_input.py src/agent_toolkit_tui/widgets/skill_grid.py tests/test_tui/test_skill_grid_filter.py
git commit -m "refactor(tui): share grid filter input"
```

## Task 2: Add non-skill filter regression tests

**Files:**
- Create: `tests/test_tui/test_asset_grid_filters.py`
- Read existing factories in:
  - `tests/test_tui/test_agent_grid.py`
  - `tests/test_tui/test_instruction_grid.py`
  - `tests/test_tui/test_command_grid.py`
  - `tests/test_tui/test_pi_grid.py`
  - `tests/test_tui/test_mcp_grid.py`

- [ ] **Step 1: Create test helper file with concrete AgentGrid coverage**

Create `tests/test_tui/test_asset_grid_filters.py`:

```python
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Input

from agent_toolkit_tui.agent_state import AgentCell, AgentRow
from agent_toolkit_tui.composition import INTERACTIVE_HARNESSES
from agent_toolkit_tui.widgets.agent_grid import AgentGrid


def _agent_row(slug: str, *, linked: bool = False) -> AgentRow:
    return AgentRow(
        slug=slug,
        source="owner/repo",
        ref="main",
        cells={(INTERACTIVE_HARNESSES[0], "global"): AgentCell(linked=linked)},
    )


def _slugs(table: DataTable) -> list[str]:
    return [str(table.get_row_at(i)[0]) for i in range(table.row_count)]


class AgentGridApp(App[None]):
    def compose(self) -> ComposeResult:
        yield AgentGrid(
            [
                _agent_row("alpha"),
                _agent_row("beta"),
                _agent_row("gamma"),
            ],
            id="agent-grid",
        )


@pytest.mark.asyncio
async def test_agent_filter_matches_slug_case_insensitively():
    app = AgentGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#agent-grid", AgentGrid)
        table = app.query_one("#agent-table", DataTable)

        grid.set_filter("BETA")
        await pilot.pause()

        assert _slugs(table) == ["beta"]
        assert grid.row_count == 3


@pytest.mark.asyncio
async def test_agent_filter_typing_narrows_rows():
    app = AgentGridApp()
    async with app.run_test() as pilot:
        app.query_one("#agent-filter", Input).focus()
        await pilot.press("b", "e")

        table = app.query_one("#agent-table", DataTable)
        assert _slugs(table) == ["beta"]


@pytest.mark.asyncio
async def test_agent_filter_focus_handoff_keys():
    app = AgentGridApp()
    async with app.run_test() as pilot:
        app.query_one("#agent-filter", Input).focus()
        await pilot.press("down")
        assert app.focused is not None
        assert app.focused.id == "agent-table"

        app.query_one("#agent-filter", Input).focus()
        await pilot.press("tab")
        assert app.focused is not None
        assert app.focused.id == "agent-table"

        app.query_one("#agent-filter", Input).focus()
        await pilot.press("enter")
        assert app.focused is not None
        assert app.focused.id == "agent-table"


@pytest.mark.asyncio
async def test_agent_toggle_after_filter_targets_visible_row():
    app = AgentGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#agent-grid", AgentGrid)
        table = app.query_one("#agent-table", DataTable)
        grid.set_filter("beta")
        await pilot.pause()

        table.cursor_coordinate = table.cursor_coordinate.with_column(1)
        table.focus()
        await pilot.press("space")

        assert list(grid.pending_entries()) == [("global", INTERACTIVE_HARNESSES[0], "beta")]


@pytest.mark.asyncio
async def test_agent_zero_match_row_actions_noop():
    app = AgentGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#agent-grid", AgentGrid)
        table = app.query_one("#agent-table", DataTable)
        grid.set_filter("zzz")
        await pilot.pause()

        assert table.row_count == 0
        await pilot.press("space")
        await pilot.press("i")
        assert grid.pending_entries() == {}


@pytest.mark.asyncio
async def test_agent_bulk_action_ignores_filter():
    app = AgentGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#agent-grid", AgentGrid)
        table = app.query_one("#agent-table", DataTable)
        grid.set_filter("beta")
        await pilot.pause()

        table.cursor_coordinate = table.cursor_coordinate.with_column(1)
        table.focus()
        await pilot.press("a")

        pending_slugs = {key[2] for key in grid.pending_entries()}
        assert pending_slugs == {"alpha", "beta", "gamma"}
```

- [ ] **Step 2: Run new tests to verify failure**

Run:

```bash
uv run pytest tests/test_tui/test_asset_grid_filters.py -q
```

Expected: FAIL because `#agent-filter` and `AgentGrid.set_filter()` do not exist yet.

- [ ] **Step 3: Add at least one extra pane smoke test**

Extend the same file with one instruction-pane smoke test using inline rows:

```python
from agent_toolkit_tui.composition import INTERACTIVE_HARNESSES
from agent_toolkit_tui.instruction_state import InstructionCell, InstructionRow
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid


def _instruction_row(slug: str) -> InstructionRow:
    return InstructionRow(
        slug=slug,
        source="AGENTS.md",
        cells={
            (harness, "global"): InstructionCell(linked=False, conflict=False)
            for harness in INTERACTIVE_HARNESSES
        },
    )


class InstructionGridApp(App[None]):
    def compose(self) -> ComposeResult:
        yield InstructionGrid(
            [_instruction_row("AGENTS.md"), _instruction_row("GEMINI.md")],
            id="instruction-grid",
        )


@pytest.mark.asyncio
async def test_instruction_filter_smoke():
    app = InstructionGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#instruction-grid", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        grid.set_filter("gem")
        await pilot.pause()

        assert _slugs(table) == ["GEMINI.md"]
        assert grid.row_count == 2
```

Expected after Step 2 remains FAIL until widget implementation lands.

## Task 3: Add filter state to AgentGrid and InstructionGrid

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/agent_grid.py`
- Modify: `src/agent_toolkit_tui/widgets/instruction_grid.py`
- Test: `tests/test_tui/test_asset_grid_filters.py`

- [ ] **Step 1: Add common imports and filter fields**

In both files, change widget imports from:

```python
from textual.widgets import DataTable
```

to:

```python
from textual.widgets import DataTable, Input
```

Add:

```python
from agent_toolkit_tui.widgets.filter_input import GridFilterInput
```

In each `__init__()`, after `_pending` setup, add:

```python
self._filter: str = ""
```

- [ ] **Step 2: Render filter input before the table**

In `AgentGrid.compose()`, yield filter before table:

```python
yield GridFilterInput(table_selector="#agent-table", id="agent-filter")
table: DataTable[str] = DataTable(
    id="agent-table", cursor_type="cell", zebra_stripes=True,
)
yield table
```

In `InstructionGrid.compose()`, yield filter before table:

```python
yield GridFilterInput(table_selector="#instruction-table", id="instruction-filter")
table: DataTable[str] = DataTable(
    id="instruction-table", cursor_type="cell", zebra_stripes=True,
)
yield table
```

- [ ] **Step 3: Add filter methods and input handlers**

In `AgentGrid`, add:

```python
def set_filter(self, text: str) -> None:
    self._filter = text.strip().lower()
    try:
        table = self.query_one("#agent-table", DataTable)
    except Exception:
        return
    self._rebuild(table)


def _visible_rows(self) -> list[AgentRow]:
    if self._filter:
        return [row for row in self._rows if self._filter in row.slug.lower()]
    return list(self._rows)


def on_input_changed(self, event: Input.Changed) -> None:
    if event.input.id == "agent-filter":
        self.set_filter(event.value)


def on_input_submitted(self, event: Input.Submitted) -> None:
    if event.input.id == "agent-filter":
        try:
            self.query_one("#agent-table", DataTable).focus()
        except Exception:
            pass
```

In `InstructionGrid`, add the same methods with `InstructionRow`, `#instruction-table`, and `instruction-filter`.

- [ ] **Step 4: Rebuild from visible rows and clamp cursor safely**

In both `_rebuild()` methods, preserve the existing columns and row cell construction, but replace the row loop:

```python
visible = self._visible_rows()
for row in visible:
    ...
```

Replace cursor restoration with this pattern while keeping each file's current `max_col` calculation line unchanged:

```python
if visible:
    max_row = len(visible) - 1
    table.cursor_coordinate = Coordinate(
        row=min(saved.row, max_row),
        column=min(saved.column, max_col),
    )
table.scroll_to(x=saved_scroll[0], y=saved_scroll[1], animate=False, force=True)
```

Do not change column order, labels, glyphs, or state markup.

- [ ] **Step 5: Map row-targeted actions through visible rows**

In `AgentGrid.action_info()`, `AgentGrid._context_for()`, and `AgentGrid._toggle_at()`, replace direct `self._rows[coord.row]` / `self._rows[row_index]` lookups with:

```python
visible = self._visible_rows()
if coord.row >= len(visible):
    return
row = visible[coord.row]
```

For `_context_for()`:

```python
visible = self._visible_rows()
if row_index < 0 or row_index >= len(visible):
    return None
row = visible[row_index]
```

Make the same changes in `InstructionGrid.action_info()`, `InstructionGrid._context_for()`, and `InstructionGrid._toggle_at()`.

Leave `action_toggle_column()` loops over `self._rows` unchanged.

- [ ] **Step 6: Run focused filter tests**

Run:

```bash
uv run pytest tests/test_tui/test_asset_grid_filters.py -q
```

Expected: PASS for AgentGrid and InstructionGrid tests after fixing any exact constructor mismatch.

- [ ] **Step 7: Commit Agent/Instruction filters**

```bash
git add src/agent_toolkit_tui/widgets/agent_grid.py src/agent_toolkit_tui/widgets/instruction_grid.py tests/test_tui/test_asset_grid_filters.py
git commit -m "feat(tui): filter agent and instruction grids"
```

## Task 4: Add filters to Command, Pi Extension, and MCP grids

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/command_grid.py`
- Modify: `src/agent_toolkit_tui/widgets/pi_grid.py`
- Modify: `src/agent_toolkit_tui/widgets/mcp_grid.py`
- Test: `tests/test_tui/test_asset_grid_filters.py`

- [ ] **Step 1: Add imports and `_filter` fields**

In each file, import `Input` and `GridFilterInput`:

```python
from textual.widgets import DataTable, Input
from agent_toolkit_tui.widgets.filter_input import GridFilterInput
```

Add `self._filter: str = ""` in each grid `__init__()`.

- [ ] **Step 2: Add filter inputs with stable IDs**

In `CommandGrid.compose()`:

```python
yield GridFilterInput(table_selector="#command-table", id="command-filter")
```

In `PiGrid.compose()`:

```python
yield GridFilterInput(table_selector="#pi-table", id="pi-filter")
```

In `McpGrid.compose()`:

```python
yield GridFilterInput(table_selector="#mcp-table", id="mcp-filter")
```

Each filter yield must come immediately before that grid's existing `DataTable` yield.

- [ ] **Step 3: Add per-grid filter methods**

Use this exact structure in `CommandGrid`:

```python
def set_filter(self, text: str) -> None:
    self._filter = text.strip().lower()
    try:
        table = self.query_one("#command-table", DataTable)
    except Exception:
        return
    self._rebuild(table)


def _visible_rows(self) -> list[CommandRow]:
    if self._filter:
        return [row for row in self._rows if self._filter in row.slug.lower()]
    return list(self._rows)


def on_input_changed(self, event: Input.Changed) -> None:
    if event.input.id == "command-filter":
        self.set_filter(event.value)


def on_input_submitted(self, event: Input.Submitted) -> None:
    if event.input.id == "command-filter":
        try:
            self.query_one("#command-table", DataTable).focus()
        except Exception:
            pass
```

Use the same structure for `PiGrid` with `PiExtensionRow`, `#pi-table`, `pi-filter`; and `McpGrid` with `McpRow`, `#mcp-table`, `mcp-filter`.

- [ ] **Step 4: Rebuild from visible rows**

In each `_rebuild()`, replace `for row in self._rows:` with visible-row iteration:

```python
visible = self._visible_rows()
for row in visible:
    ...
```

Clamp cursor only when `visible` is non-empty. Preserve each existing `max_col` calculation and `scroll_to()` call.

- [ ] **Step 5: Map row-targeted actions through visible rows**

In `CommandGrid`, `PiGrid`, and `McpGrid`, update `_toggle_at()`, `action_info()`, and `_context_for()` to use `_visible_rows()` exactly as in Task 3.

If one of these grids has an info helper that receives `row_index`, keep helper signature unchanged and translate `row_index` to visible row inside the helper.

Leave `action_toggle_column()` loops over `self._rows` unchanged.

- [ ] **Step 6: Add one smoke assertion per remaining grid**

Extend `tests/test_tui/test_asset_grid_filters.py` with one smoke test each for `CommandGrid`, `PiGrid`, and `McpGrid`. Each test should:

1. Mount two rows with distinct slugs.
2. Call `grid.set_filter()` with a substring matching only the second slug.
3. Assert the table shows only the matched slug.
4. Assert `grid.row_count == 2`.

Use each row dataclass's existing minimal constructors from current grid tests. The command example should look like:

```python
from agent_toolkit_tui.command_state import CommandCell, CommandRow
from agent_toolkit_tui.widgets.command_grid import CommandGrid


def _command_row(slug: str) -> CommandRow:
    return CommandRow(
        slug=slug,
        source="owner/repo",
        ref="main",
        cells={(INTERACTIVE_HARNESSES[0], "global"): CommandCell(linked=False)},
    )
```

Add concrete helpers for Pi and MCP in the same test file:

```python
from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
from agent_toolkit_tui.widgets.pi_grid import PiGrid
from agent_toolkit_tui.mcp_state import McpCell, McpRow
from agent_toolkit_tui.widgets.mcp_grid import McpGrid


def _pi_row(slug: str) -> PiExtensionRow:
    cell = PiCell(global_loaded=False, project_loaded=False, origin="store-owned")
    return PiExtensionRow(
        slug=slug,
        origin="store-owned",
        source=f"git@github.com:x/{slug}",
        global_cell=cell,
        project_cell=cell,
    )


def _mcp_row(slug: str) -> McpRow:
    return McpRow(
        slug=slug,
        source="npx",
        pin=None,
        state="installed",
        cells={("standard", "project"): McpCell(linked=False)},
    )
```

Use these helpers in the Pi and MCP smoke tests.

- [ ] **Step 7: Run grid filter tests**

Run:

```bash
uv run pytest tests/test_tui/test_asset_grid_filters.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit remaining grid filters**

```bash
git add src/agent_toolkit_tui/widgets/command_grid.py src/agent_toolkit_tui/widgets/pi_grid.py src/agent_toolkit_tui/widgets/mcp_grid.py tests/test_tui/test_asset_grid_filters.py
git commit -m "feat(tui): filter command pi and mcp grids"
```

## Task 5: Route `/` to the active pane filter

**Files:**
- Modify: `src/agent_toolkit_tui/app.py`
- Test: `tests/test_tui/test_app_filter_focus.py`

- [ ] **Step 1: Write failing app focus tests**

Create `tests/test_tui/test_app_filter_focus.py`:

```python
from __future__ import annotations

import pytest

from agent_toolkit_tui.app import TUIApp


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("asset_type", "filter_id"),
    [
        ("instruction", "instruction-filter"),
        ("skill", "skill-filter"),
        ("command", "command-filter"),
        ("pi-extension", "pi-filter"),
        ("agent", "agent-filter"),
        ("mcp", "mcp-filter"),
    ],
)
async def test_slash_focuses_active_asset_filter(asset_type: str, filter_id: str):
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type(asset_type)
        await pilot.pause()

        await pilot.press("/")
        await pilot.pause()

        assert app.focused is not None
        assert app.focused.id == filter_id
```

- [ ] **Step 2: Run app focus tests to verify failure**

Run:

```bash
uv run pytest tests/test_tui/test_app_filter_focus.py -q
```

Expected: FAIL because `action_focus_filter()` still focuses `#skill-filter` for every asset type.

- [ ] **Step 3: Implement active filter routing**

In `src/agent_toolkit_tui/app.py`, update `action_focus_filter()`:

```python
def action_focus_filter(self) -> None:
    """`/` re-focuses the active asset pane's filter box."""
    selectors: dict[AssetType, str] = {
        "instruction": "#instruction-filter",
        "skill": "#skill-filter",
        "command": "#command-filter",
        "pi-extension": "#pi-filter",
        "agent": "#agent-filter",
        "mcp": "#mcp-filter",
    }
    try:
        self.query_one(selectors[self._asset_type], Input).focus()
    except Exception:
        pass
```

Ensure `Input` remains imported in `app.py`.

- [ ] **Step 4: Run app focus tests**

Run:

```bash
uv run pytest tests/test_tui/test_app_filter_focus.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit focus routing**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_app_filter_focus.py
git commit -m "feat(tui): focus active asset filter"
```

## Task 6: Full regression and cleanup

**Files:**
- Review: `src/agent_toolkit_tui/widgets/*.py`
- Review: `tests/test_tui/test_asset_grid_filters.py`
- Review: `tests/test_tui/test_app_filter_focus.py`

- [ ] **Step 1: Run focused Skills regression**

Run:

```bash
uv run pytest tests/test_tui/test_skill_grid_filter.py -q
```

Expected: PASS.

- [ ] **Step 2: Run new filter suite**

Run:

```bash
uv run pytest tests/test_tui/test_asset_grid_filters.py tests/test_tui/test_app_filter_focus.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full TUI suite**

Run:

```bash
uv run pytest tests/test_tui -q
```

Expected: PASS.

- [ ] **Step 4: Search for stale hard-coded Skills focus assumptions**

Run:

```bash
rg "skill-filter|focus_filter|set_filter|_visible_rows" src/agent_toolkit_tui tests/test_tui
```

Expected:

- `skill-filter` remains in Skills-specific tests and app filter selector map only.
- `focus_filter` maps all active asset types.
- Every non-skill grid has `set_filter()` and `_visible_rows()`.

- [ ] **Step 5: Manual TUI smoke check**

Run:

```bash
uv run agent-toolkit-tui
```

Manual checks:

1. Open each asset type from sidebar.
2. Press `/`; focus lands in visible pane's filter.
3. Type a substring; visible rows narrow.
4. Press Down; focus moves into that pane's table.
5. Press `Esc` or quit according to current TUI bindings.

Capture a short note in PR body with panes checked and any pane that could not be checked because local data was unavailable.

- [ ] **Step 6: Final commit if cleanup changed files**

If Step 4 or Step 5 required cleanup:

```bash
git add src/agent_toolkit_tui tests/test_tui
git commit -m "test(tui): cover asset filter regressions"
```

## Risk controls

- Do not change data model dataclasses.
- Do not change existing pending key shapes.
- Do not change `action_toggle_column()` full-row loops.
- Do not change table column order or column labels while adding filters.
- If a grid's row-targeted info path has ambiguous row-index behavior, stop and add a failing test before editing it.

## Self-review checklist

- Spec coverage: every acceptance criterion maps to Tasks 1–6.
- Placeholder scan: no implementation step contains unresolved placeholders.
- Type consistency: filter IDs and table IDs match spec exactly.
- Test-first coverage: Task 2 and Task 5 add failing tests before implementation.
- Scope guard: plan does not introduce fuzzy search, highlighting, sorting, or base-class refactor.
