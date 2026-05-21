# TUI Cosmetic Header Polish + State Info Popup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `SkillGrid` headers (`slug→SKILL`, `(i) universal→Universal (i)`, `state→State (i)`) and add a `state` entry in `COLUMN_INFO` with a five-badge legend, so pressing `i` on a state cell opens `ColumnInfoModal`.

**Architecture:** Two source files change. `column_info.py` gains a `_state_info()` factory + a registry entry. `widgets/skill_grid.py` changes the header label composition (capitalised base, glyph suffixed), adds a new helper `_column_key_for_index` used only by the `i` action, and updates the `state` column header conditionally. Three test files update string assertions and add coverage for the new state popup. No behaviour change to badge rendering, link/unlink machinery, or `INTERACTIVE_AGENTS`.

**Tech Stack:** Python 3.12, Textual 0.79+, pytest 8 (with `pytest-asyncio` in auto mode), `uv` for the runner.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/agent_toolkit_tui/column_info.py` | Per-column info registry. | Add `_state_info()` factory + `"state"` entry in `COLUMN_INFO`. |
| `src/agent_toolkit_tui/widgets/skill_grid.py` | Renders the DataTable + handles keystrokes. | Change `_rebuild` header strings; add `_column_key_for_index` helper; wire `action_open_column_info` through it. |
| `tests/test_tui/test_column_info.py` | Tests for the info registry. | Add tests for the `"state"` entry. |
| `tests/test_tui/test_skill_grid_column_info.py` | Tests for `SkillGrid`'s i-key wiring + header strings. | Update existing string assertions; add a test for `i` on the state column. |
| `tests/test_tui/test_skill_grid_apply.py` | Tests for SkillGrid apply/toggle flows. | Audit only — change only if it asserts old header strings. |

---

## Task 1: Add `_state_info` factory + register in `COLUMN_INFO`

**Files:**
- Modify: `src/agent_toolkit_tui/column_info.py`
- Test: `tests/test_tui/test_column_info.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tui/test_column_info.py`:

```python
def test_state_entry_is_registered():
    assert "state" in COLUMN_INFO


def test_get_column_info_state_returns_columninfo():
    info = get_column_info("state")
    assert isinstance(info, ColumnInfo)
    assert info.title == "State badges"


def test_get_column_info_state_lists_all_five_badges():
    info = get_column_info("state")
    text = "\n".join(info.lines)
    for badge in ("clean", "dirty", "missing", "copy", "library"):
        assert badge in text, f"badge {badge!r} missing from state info"


def test_get_column_info_state_badge_order_matches_state_markup():
    """Order matches _STATE_MARKUP declaration order, with `library` last."""
    info = get_column_info("state")
    bullets = [ln for ln in info.lines if ln.lstrip().startswith("•")]
    badges = [ln.split("—")[0].strip().lstrip("• ").strip() for ln in bullets]
    assert badges == ["clean", "dirty", "missing", "copy", "library"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_tui/test_column_info.py -v
```

Expected: the four new tests fail with `KeyError: 'state'` or assertion failures because `"state"` is not yet in `COLUMN_INFO`. The existing `test_universal_*` tests still pass.

- [ ] **Step 3: Add the factory and registry entry**

Modify `src/agent_toolkit_tui/column_info.py`. Add `_state_info` above `COLUMN_INFO`, then add the registry entry.

After the existing `_universal_info` function, insert:

```python
def _state_info() -> ColumnInfo:
    # Source of truth for badge meaning: _STATE_MARKUP in
    # agent_toolkit_tui/widgets/skill_grid.py (declaration order preserved).
    return ColumnInfo(
        title="State badges",
        lines=[
            "Per-skill working-tree state in this scope.",
            "",
            "• clean — installed and matches the library canonical",
            "• dirty — installed but the on-disk copy diverges from the library",
            "• missing — in the library, not installed in this scope",
            "• copy — installed as a real copy (symlink fallback — e.g. Windows)",
            "• library — in the library, not yet installed in this project "
            "(project scope only — normal pre-install state)",
        ],
    )
```

Then change the `COLUMN_INFO` dict from:

```python
COLUMN_INFO: dict[str, Callable[[], ColumnInfo]] = {
    "universal": _universal_info,
}
```

to:

```python
COLUMN_INFO: dict[str, Callable[[], ColumnInfo]] = {
    "universal": _universal_info,
    "state": _state_info,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_tui/test_column_info.py -v
```

Expected: all tests (existing + new) pass.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/column_info.py tests/test_tui/test_column_info.py
git commit -m "feat(tui): add 'state' column-info entry with badge legend (#179)"
```

---

## Task 2: Add `_column_key_for_index` helper (resolves col → registry key)

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py:229-235`
- Test: `tests/test_tui/test_skill_grid_column_info.py`

**Why this helper, not extending `_agent_for_column`:** `_agent_for_column` is also called by `action_toggle_column` (the `a` keystroke). Returning `"state"` from there would let the user accidentally try to toggle the state column. Keeping `_agent_for_column` strictly about agents and adding a parallel resolver for the `i` action is cleaner.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tui/test_skill_grid_column_info.py`:

```python
@pytest.mark.asyncio
async def test_column_key_for_index_resolves_state():
    from textual.app import App
    from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        state_col = 1 + len(INTERACTIVE_AGENTS)
        assert g._column_key_for_index(0) is None
        assert g._column_key_for_index(state_col) == "state"
        for i, agent in enumerate(INTERACTIVE_AGENTS, start=1):
            assert g._column_key_for_index(i) == agent
        assert g._column_key_for_index(state_col + 1) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_tui/test_skill_grid_column_info.py::test_column_key_for_index_resolves_state -v
```

Expected: `AttributeError: 'SkillGrid' object has no attribute '_column_key_for_index'`.

- [ ] **Step 3: Add the helper**

Modify `src/agent_toolkit_tui/widgets/skill_grid.py`. Locate `_agent_for_column` (lines 229-235). Immediately after it, add:

```python
    def _column_key_for_index(self, col: int) -> str | None:
        """Resolve a column index to a COLUMN_INFO key.

        Layout: [0]=slug, [1..N]=INTERACTIVE_AGENTS, [N+1]=state.
        Returns None for unknown indices (including col 0; "slug" is not in
        the info registry today).
        """
        if col == 0:
            return None
        n = len(INTERACTIVE_AGENTS)
        if 1 <= col <= n:
            return INTERACTIVE_AGENTS[col - 1]
        if col == n + 1:
            return "state"
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_tui/test_skill_grid_column_info.py::test_column_key_for_index_resolves_state -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py tests/test_tui/test_skill_grid_column_info.py
git commit -m "feat(tui): add _column_key_for_index for i-key column routing (#179)"
```

---

## Task 3: Route `action_open_column_info` through the new helper

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py:178-191`
- Test: `tests/test_tui/test_skill_grid_column_info.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tui/test_skill_grid_column_info.py`:

```python
@pytest.mark.asyncio
async def test_press_i_on_state_column_opens_modal():
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable
    from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        state_col = 1 + len(INTERACTIVE_AGENTS)
        table.cursor_coordinate = Coordinate(row=0, column=state_col)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert any(isinstance(s, ColumnInfoModal) for s in a.screen_stack), \
            "ColumnInfoModal not pushed when pressing i on state column"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_tui/test_skill_grid_column_info.py::test_press_i_on_state_column_opens_modal -v
```

Expected: assertion failure — `_agent_for_column` returns `None` for col `N+1`, so `action_open_column_info` returns early and never pushes the modal.

- [ ] **Step 3: Update `action_open_column_info`**

Modify `src/agent_toolkit_tui/widgets/skill_grid.py`. Replace the existing `action_open_column_info` (lines 178-191):

Current:

```python
    def action_open_column_info(self) -> None:
        """Open ColumnInfoModal for the column under the cursor, if registered."""
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        col = table.cursor_coordinate.column
        agent = self._agent_for_column(col)
        if agent is None:
            return
        info = get_column_info(agent)
        if info is None:
            return
        self.app.push_screen(ColumnInfoModal(info))
```

Replace with:

```python
    def action_open_column_info(self) -> None:
        """Open ColumnInfoModal for the column under the cursor, if registered."""
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        col = table.cursor_coordinate.column
        key = self._column_key_for_index(col)
        if key is None:
            return
        info = get_column_info(key)
        if info is None:
            return
        self.app.push_screen(ColumnInfoModal(info))
```

- [ ] **Step 4: Run targeted + full grid-info tests**

Run:

```bash
uv run pytest tests/test_tui/test_skill_grid_column_info.py -v
```

Expected: all tests pass — the new `test_press_i_on_state_column_opens_modal` passes, and `test_press_i_on_universal_column_opens_modal`, `test_press_i_on_claude_code_column_is_noop`, `test_press_i_on_slug_column_is_noop` still pass.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py tests/test_tui/test_skill_grid_column_info.py
git commit -m "feat(tui): route i-key through _column_key_for_index so state opens modal (#179)"
```

---

## Task 4: Rename headers — SKILL / Universal (i) / State (i)

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py:237-247`
- Test: `tests/test_tui/test_skill_grid_column_info.py`

- [ ] **Step 1: Write the failing tests**

Append three new tests to `tests/test_tui/test_skill_grid_column_info.py` and modify the existing `test_universal_column_label_has_info_glyph` to assert the new format.

First, replace `test_universal_column_label_has_info_glyph`:

```python
@pytest.mark.asyncio
async def test_universal_column_label_has_info_glyph():
    """The universal column label is 'Universal ⓘ'; agent columns have no glyph."""
    from textual.app import App
    from textual.widgets import DataTable

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        # Layout: SKILL | Universal ⓘ | Claude Code | Pi | State ⓘ
        assert labels[1] == "Universal ⓘ", f"universal label: {labels[1]!r}"
        assert "ⓘ" not in labels[2], f"claude-code label has glyph: {labels[2]!r}"
        assert "ⓘ" not in labels[3], f"pi label has glyph: {labels[3]!r}"
```

Then append three new tests:

```python
@pytest.mark.asyncio
async def test_slug_header_is_uppercase():
    from textual.app import App
    from textual.widgets import DataTable

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert labels[0] == "SKILL", f"slug header: {labels[0]!r}"


@pytest.mark.asyncio
async def test_state_header_is_capitalised_with_glyph():
    from textual.app import App
    from textual.widgets import DataTable
    from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        state_col = 1 + len(INTERACTIVE_AGENTS)
        assert labels[state_col] == "State ⓘ", f"state header: {labels[state_col]!r}"


@pytest.mark.asyncio
async def test_full_header_row():
    """Header row matches spec exactly."""
    from textual.app import App
    from textual.widgets import DataTable

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert labels == ["SKILL", "Universal ⓘ", "Claude Code", "Pi", "State ⓘ"], \
            f"unexpected header row: {labels!r}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_tui/test_skill_grid_column_info.py -v -k "header or label"
```

Expected: the four header/label tests fail. Current labels are `["slug", "ⓘ universal", "Claude Code", "Pi", "state"]`.

- [ ] **Step 3: Update `_rebuild`**

Modify `src/agent_toolkit_tui/widgets/skill_grid.py`. Replace lines 237-247 (the `_rebuild` header section).

Current:

```python
    def _rebuild(self, table: DataTable) -> None:
        saved = table.cursor_coordinate
        table.clear(columns=True)
        table.add_column("slug", width=20)
        for agent in INTERACTIVE_AGENTS:
            # Use "universal" verbatim for the bundle column (lowercase, per spec).
            # Other agents use their catalog display_name.
            base = "universal" if agent == "universal" else AGENTS[agent].display_name
            label = f"{_INFO_GLYPH} {base}" if agent in COLUMN_INFO else base
            table.add_column(label, width=14)
        table.add_column("state", width=10)
```

Replace with:

```python
    def _rebuild(self, table: DataTable) -> None:
        saved = table.cursor_coordinate
        table.clear(columns=True)
        table.add_column("SKILL", width=20)
        for agent in INTERACTIVE_AGENTS:
            # "Universal" gets a capitalised base; per-agent columns use the
            # catalog display_name. The ⓘ glyph is suffixed for any column
            # whose key is in COLUMN_INFO.
            base = "Universal" if agent == "universal" else AGENTS[agent].display_name
            label = f"{base} {_INFO_GLYPH}" if agent in COLUMN_INFO else base
            table.add_column(label, width=14)
        state_label = f"State {_INFO_GLYPH}" if "state" in COLUMN_INFO else "State"
        table.add_column(state_label, width=10)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_tui/test_skill_grid_column_info.py -v
```

Expected: every test passes (new header tests + existing `i`-key behaviour tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py tests/test_tui/test_skill_grid_column_info.py
git commit -m "feat(tui): polish SkillGrid headers (SKILL / Universal ⓘ / State ⓘ) (#179)"
```

---

## Task 5: Sweep — module docstring + audit `test_skill_grid_apply.py`

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py:1-11` (module docstring)
- Audit only: `tests/test_tui/test_skill_grid_apply.py`

- [ ] **Step 1: Update the module docstring**

Modify `src/agent_toolkit_tui/widgets/skill_grid.py`. Replace lines 1-11 (the existing docstring):

Current:

```python
"""Interactive DataTable for the TUI's skill tab.

Columns: slug | claude-code | pi | state.

`space` toggles a cell (queues link/unlink in `_pending`).
`a` toggles a column.
`^s` Apply is handled by the App, which reads pending_entries().

The long tail of agents is managed via the CLI; the TUI grid only shows
the interactive shortlist (claude-code + pi).
"""
```

Replace with:

```python
"""Interactive DataTable for the TUI's skill tab.

Columns: SKILL | Universal ⓘ | Claude Code | Pi | State ⓘ.

`space` toggles a cell (queues link/unlink in `_pending`).
`a` toggles a column.
`i` opens ColumnInfoModal for the column under the cursor (Universal, State).
`^s` Apply is handled by the App, which reads pending_entries().

The long tail of agents is managed via the CLI; the TUI grid only shows
the interactive shortlist (universal + claude-code + pi).
"""
```

- [ ] **Step 2: Audit `tests/test_tui/test_skill_grid_apply.py` for stale header strings**

Run:

```bash
grep -n "\"slug\"\|\"state\"\|ⓘ universal\|'slug'\|'state'" tests/test_tui/test_skill_grid_apply.py
```

Expected: no hits. (The apply tests assert toggling/linking semantics, not header strings.)

If any hits appear, update them to match the new headers (`SKILL`, `State ⓘ`, `Universal ⓘ`). If no hits, proceed without changes.

- [ ] **Step 3: Run the full TUI test directory**

Run:

```bash
uv run pytest tests/test_tui/ -v
```

Expected: every test in `tests/test_tui/` passes.

- [ ] **Step 4: Run the full test suite**

Run:

```bash
uv run pytest
```

Expected: PASS. (The pre-commit hook also runs pytest, so a green run here means the commit in Step 5 will not be rejected.)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py
git commit -m "docs(tui): refresh SkillGrid module docstring for new headers (#179)"
```

If Step 2 produced any changes, include `tests/test_tui/test_skill_grid_apply.py` in the `git add`.

---

## Self-review (already run)

- **Spec coverage:** Every header rename + popup requirement maps to Task 1-4. Routing extension is Task 2-3. Module docstring sweep is Task 5. DoD bullets 1-3 covered by Task 4's `test_full_header_row` + Task 3's `test_press_i_on_state_column_opens_modal` + existing `test_press_i_on_universal_column_opens_modal`. DoD bullet 4 (pytest passes) covered by Task 5 Step 4.
- **Placeholder scan:** No "TBD", "implement later", or "similar to". Every code-changing step has the literal code.
- **Type consistency:** `_column_key_for_index` returns `str | None` in Task 2; consumed by `action_open_column_info` in Task 3 as `key`; `get_column_info(key)` accepts `str` (existing signature). `_state_info` returns `ColumnInfo` (existing dataclass). All consistent.
