# TUI Info-Panel Cosmetics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish four TUI Skills-tab info-panel cosmetics (#212): library-state row description, gated 🌐 marker text, `ⓘ` glyph coverage, and the `library` state placeholder.

**Architecture:** Presentation-layer fixes only. (1) Description falls back to the library canonical when the project canonical is absent. (2) `get_column_info()` gains an optional `context=` arg so the Universal factory can omit the global-marker paragraph when the focused row's global cell isn't linked. (3) Glyph appears on every column except `Source`. (4) Em dash substitutes for `library` in the slug-cell info body.

**Tech Stack:** Python 3.13, Textual, pytest-asyncio. Test suite already covers info panels; we extend it.

---

## Files

- Modify: `src/agent_toolkit_tui/skill_state.py` — description fallback
- Modify: `src/agent_toolkit_tui/column_info.py` — context-aware factory + signature
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py` — pass context, glyph all but Source, em-dash state in slug-cell body
- Modify: `tests/test_tui/test_skill_grid_new_columns.py` — description fallback test
- Modify: `tests/test_tui/test_column_info.py` — context arg behaviour, drop stale "🌐 always present" assertion
- Modify: `tests/test_tui/test_skill_grid_column_info.py` — update header-glyph assertions
- Modify: `tests/test_tui/test_cell_info.py` — em-dash assertion for library state

---

## Task 1: Description falls back to the library canonical

**Files:**
- Test: `tests/test_tui/test_skill_grid_new_columns.py` (extend)
- Modify: `src/agent_toolkit_tui/skill_state.py` (the `build_skill_rows` description read)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tui/test_skill_grid_new_columns.py`:

```python
def test_build_skill_rows_project_scope_falls_back_to_library_description(
    git_sandbox, tmp_path, monkeypatch,
):
    """At project scope, when the project canonical is absent (state='library'),
    SkillRow.description reads from the library canonical instead of returning empty."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main
    from agent_toolkit_tui.skill_state import build_skill_rows

    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    # Only add to library; do NOT install at project scope.
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output

    # Stamp a description into the library canonical's SKILL.md.
    library_canonical = library_root / "demo"
    skill_md = library_canonical / "SKILL.md"
    skill_md.write_text(
        "---\nname: demo\ndescription: Library description value\n---\n\nBody.\n"
    )

    rows = build_skill_rows(scope="project", home=None, project=project)
    assert len(rows) == 1
    row = rows[0]
    assert row.state == "library", f"precondition: expected state=library, got {row.state}"
    assert row.description == "Library description value", (
        f"description should fall back to the library canonical, got {row.description!r}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_skill_grid_new_columns.py::test_build_skill_rows_project_scope_falls_back_to_library_description -v`
Expected: FAIL — assertion `row.description == "Library description value"` fails (description is `""`).

- [ ] **Step 3: Implement the fallback in `build_skill_rows`**

Open `src/agent_toolkit_tui/skill_state.py`. Add the import `library_skill_path` at the top with the other `skill_paths` imports:

```python
from agent_toolkit_cli.skill_paths import (
    agent_projection_dir, canonical_skill_dir, library_lock_path,
    library_skill_path, parent_clone_path,
)
```

Replace the existing `rows.append(SkillRow(...))` call at the end of `build_skill_rows` with the fallback logic. Current code (the last `rows.append(...)`):

```python
        rows.append(SkillRow(
            slug=slug, source=entry.source, ref=entry.ref or "main",
            state=state, cells=cells,
            description=_read_skill_description(canonical),
        ))
```

becomes:

```python
        description = _read_skill_description(canonical)
        if not description and scope == "project":
            # Project canonical may be absent (state == "library") or missing
            # SKILL.md; fall back to the library copy, which is the source of
            # truth for the description anyway.
            description = _read_skill_description(library_skill_path(slug))
        rows.append(SkillRow(
            slug=slug, source=entry.source, ref=entry.ref or "main",
            state=state, cells=cells,
            description=description,
        ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_skill_grid_new_columns.py::test_build_skill_rows_project_scope_falls_back_to_library_description -v`
Expected: PASS.

- [ ] **Step 5: Run the existing description tests to confirm no regression**

Run: `uv run pytest tests/test_tui/test_skill_grid_new_columns.py tests/test_tui/test_skill_state.py -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui/skill_state.py tests/test_tui/test_skill_grid_new_columns.py
git commit -m "fix(tui): fall back to library description when project canonical is absent (#212)"
```

---

## Task 2: `get_column_info()` accepts an optional `context=`

**Files:**
- Test: `tests/test_tui/test_column_info.py` (extend + relax one existing test)
- Modify: `src/agent_toolkit_tui/column_info.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_tui/test_column_info.py`, replace the existing
`test_universal_info_mentions_global_indicator` with **two** explicit cases
(its current semantics — "🌐 paragraph always present" — is the regression we
are fixing), and add a no-context backwards-compat test. Find:

```python
def test_universal_info_mentions_global_indicator():
    """The Universal column-info popup explains the 🌐 marker (#188)."""
    info = get_column_info("universal")
    assert info is not None
    joined = "\n".join(info.lines)
    assert "🌐" in joined, f"info missing global marker glyph: {info.lines}"
    assert "global" in joined.lower(), (
        f"info should explain the marker mentions global scope: {info.lines}"
    )
```

Replace with:

```python
def test_universal_info_includes_global_marker_when_context_says_globally_linked():
    """Universal info shows the 🌐 paragraph when the focused row IS globally installed."""
    info = get_column_info("universal", context={"global_linked": True})
    assert info is not None
    joined = "\n".join(info.lines)
    assert "🌐" in joined, f"info missing global marker glyph: {info.lines}"
    assert "global" in joined.lower(), (
        f"info should explain the marker mentions global scope: {info.lines}"
    )


def test_universal_info_omits_global_marker_when_context_says_not_globally_linked():
    """Universal info OMITS the 🌐 paragraph when the focused row is NOT globally installed (#212)."""
    info = get_column_info("universal", context={"global_linked": False})
    assert info is not None
    joined = "\n".join(info.lines)
    assert "🌐" not in joined, (
        f"info should omit 🌐 marker when not globally linked, got: {info.lines}"
    )


def test_universal_info_includes_global_marker_when_no_context():
    """Without context (e.g. legacy callers) the 🌐 paragraph still appears (back-compat)."""
    info = get_column_info("universal")
    assert info is not None
    joined = "\n".join(info.lines)
    assert "🌐" in joined, f"info missing global marker glyph: {info.lines}"
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `uv run pytest tests/test_tui/test_column_info.py -v`
Expected: The two new `*context*` tests FAIL — `get_column_info()` rejects the
`context=` kwarg.

- [ ] **Step 3: Implement context-aware `get_column_info()`**

Open `src/agent_toolkit_tui/column_info.py`. Make two changes:

1. Change `_universal_info` to accept an optional context dict and gate the 🌐 block.

```python
def _universal_info(context: dict | None = None) -> ColumnInfo:
    harness_names = get_universal_agents()
    description = [
        "Toggles link/unlink for every harness whose",
        "skillsDir is `.agents/skills`.",
        "",
        "Included harnesses:",
    ]
    bullets = [
        f"  • {name} — {AGENTS[name].display_name}"
        for name in harness_names
    ]
    # The 🌐 marker block is contextual: it only makes sense when the focused
    # row IS installed globally. Omit it when the caller says otherwise.
    show_marker = context is None or bool(context.get("global_linked", True))
    indicator_note = [
        "",
        "🌐 marker (project scope only):",
        "  This skill is also installed globally,",
        "  so you may not need it at project scope too.",
    ] if show_marker else []
    return ColumnInfo(
        title="Universal bundle",
        lines=description + bullets + indicator_note,
    )
```

2. Change `_state_info` to also accept the optional context (it ignores it,
   but the registry type must stay uniform). And update `get_column_info()`:

```python
def _state_info(context: dict | None = None) -> ColumnInfo:
    # (body unchanged — context is accepted for uniformity but not consulted)
    ...
```

```python
COLUMN_INFO: dict[str, Callable[..., ColumnInfo]] = {
    "universal": _universal_info,
    "state": _state_info,
}


def get_column_info(name: str, *, context: dict | None = None) -> ColumnInfo | None:
    """Return a fresh ColumnInfo for `name`, or None if unregistered.

    `context` is forwarded to the factory. Today only `_universal_info` reads
    it (`global_linked` flag).
    """
    factory = COLUMN_INFO.get(name)
    if factory is None:
        return None
    return factory(context)
```

Keep the `_state_info` body the same — just add the parameter so the type
annotation `Callable[..., ColumnInfo]` matches. Don't change its bullets.

- [ ] **Step 4: Run the column-info tests**

Run: `uv run pytest tests/test_tui/test_column_info.py -v`
Expected: All PASS.

- [ ] **Step 5: Run the broader column-info modal tests to check the call sites still work**

Run: `uv run pytest tests/test_tui/test_column_info_modal.py tests/test_tui/test_skill_grid_column_info.py -v`
Expected: All PASS. (Existing callers pass no `context=`, hit the back-compat path.)

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui/column_info.py tests/test_tui/test_column_info.py
git commit -m "fix(tui): gate universal-info 🌐 paragraph on focused row's global state (#212)"
```

---

## Task 3: SkillGrid passes context to `get_column_info`

**Files:**
- Test: `tests/test_tui/test_skill_grid_column_info.py` (extend)
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py` (`action_info`, `action_open_column_info`)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tui/test_skill_grid_column_info.py`:

```python
@pytest.mark.asyncio
async def test_universal_modal_omits_global_marker_when_not_globally_linked():
    """In project scope, opening the Universal column info on a row whose global
    cell is NOT linked produces a modal without the 🌐 marker paragraph (#212)."""
    from textual.app import App

    from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow

    # Project-scope row with global cells populated but NOT linked.
    cells = {}
    for a in INTERACTIVE_AGENTS:
        cells[(a, "project")] = SkillCell(linked=False, drift=False, skipped=False)
        cells[(a, "global")] = SkillCell(linked=False, drift=False, skipped=False)
    row = SkillRow(slug="alpha", source="x/alpha", ref="main", state="library", cells=cells)

    class _A(App):
        def compose(self):
            grid = SkillGrid([row], id="g")
            grid.set_scope("project")
            yield grid

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="alpha", agent_name="universal")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, ColumnInfoModal)
        text = "\n".join(a.screen._info.lines)
        assert "🌐" not in text, f"unexpected 🌐 in modal: {a.screen._info.lines}"


@pytest.mark.asyncio
async def test_universal_modal_keeps_global_marker_when_globally_linked():
    """In project scope, opening the Universal column info on a row whose global
    cell IS linked still includes the 🌐 marker paragraph."""
    from textual.app import App

    from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow

    cells = {}
    for a in INTERACTIVE_AGENTS:
        cells[(a, "project")] = SkillCell(linked=False, drift=False, skipped=False)
        cells[(a, "global")] = SkillCell(linked=False, drift=False, skipped=False)
    # The universal global cell is linked — caller has the skill globally installed.
    cells[("universal", "global")] = SkillCell(linked=True, drift=False, skipped=False)
    row = SkillRow(slug="alpha", source="x/alpha", ref="main", state="library", cells=cells)

    class _A(App):
        def compose(self):
            grid = SkillGrid([row], id="g")
            grid.set_scope("project")
            yield grid

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="alpha", agent_name="universal")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, ColumnInfoModal)
        text = "\n".join(a.screen._info.lines)
        assert "🌐" in text, f"expected 🌐 in modal: {a.screen._info.lines}"
```

If `ColumnInfoModal` exposes `_info` privately, that's fine for tests; if it
doesn't, fetch the rendered content via `a.screen.query_one(...)`. Check first
by reading the modal source — if the test needs adjustment, do it before
running step 2.

- [ ] **Step 2: Verify modal API**

Read `src/agent_toolkit_tui/widgets/column_info_modal.py` and confirm how the
modal stores the ColumnInfo. If it stores it as `self._info`, the tests above
are correct. If a different attribute, update the test to match. Then:

Run: `uv run pytest tests/test_tui/test_skill_grid_column_info.py::test_universal_modal_omits_global_marker_when_not_globally_linked tests/test_tui/test_skill_grid_column_info.py::test_universal_modal_keeps_global_marker_when_globally_linked -v`
Expected: Both FAIL — currently `action_open_column_info` calls
`get_column_info(key)` without context, so the 🌐 paragraph is always present.

- [ ] **Step 3: Pass context from `action_open_column_info`**

Open `src/agent_toolkit_tui/widgets/skill_grid.py`. In `action_open_column_info`:

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
        context = self._context_for(key=key, row_index=table.cursor_coordinate.row)
        info = get_column_info(key, context=context)
        if info is None:
            return
        self.app.push_screen(ColumnInfoModal(info))
```

Also update `action_info` (the one branch that calls
`get_column_info(col_key) is not None` to decide routing) to pass context
through there too — keep the routing predicate by checking the un-contexted
call (`get_column_info(col_key) is not None` continues to work since `state`
factory is unconditional). No change needed in `action_info`'s dispatch
predicate. The modal-opening path is the only one that needs the context.

Add a private helper `_context_for` on `SkillGrid`:

```python
    def _context_for(self, *, key: str, row_index: int) -> dict | None:
        """Build the per-call context dict for get_column_info().

        Today only the 'universal' key uses it: we surface whether the focused
        row is also installed globally so the modal can omit the 🌐 paragraph
        when it's not.
        """
        if key != "universal":
            return None
        if row_index < 0 or row_index >= len(self._rows):
            return None
        row = self._rows[row_index]
        global_cell = row.cells.get(("universal", "global"))
        return {"global_linked": bool(global_cell and global_cell.linked)}
```

- [ ] **Step 4: Run the new tests**

Run: `uv run pytest tests/test_tui/test_skill_grid_column_info.py -v`
Expected: All PASS, including the two new ones.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py tests/test_tui/test_skill_grid_column_info.py
git commit -m "fix(tui): pass focused-row global state to Universal column info (#212)"
```

---

## Task 4: `ⓘ` glyph on every column except Source

**Files:**
- Modify: `tests/test_tui/test_skill_grid_column_info.py` (update existing assertions)
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py` (`_rebuild`)

- [ ] **Step 1: Update the existing header-row tests to encode the new contract**

Open `tests/test_tui/test_skill_grid_column_info.py` and replace the body of
`test_universal_column_label_has_info_glyph` so it asserts the new shape:

```python
@pytest.mark.asyncio
async def test_columns_have_info_glyph_except_source():
    """Every column whose cells expose an info panel gets ⓘ; Source is passive (#212)."""
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
        # Layout: SKILL | Universal | Claude Code | Pi | State | Source
        assert labels[0] == "SKILL ⓘ", f"slug label: {labels[0]!r}"
        assert labels[1] == "Universal ⓘ", f"universal label: {labels[1]!r}"
        assert labels[2] == "Claude Code ⓘ", f"claude-code label: {labels[2]!r}"
        assert labels[3] == "Pi ⓘ", f"pi label: {labels[3]!r}"
        assert labels[-2] == "State ⓘ", f"state label: {labels[-2]!r}"
        assert labels[-1] == "Source", f"source label: {labels[-1]!r}"
        assert "ⓘ" not in labels[-1], f"source must not have glyph: {labels[-1]!r}"
```

Also update `test_full_header_row` to match:

```python
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
        assert labels == [
            "SKILL ⓘ", "Universal ⓘ", "Claude Code ⓘ", "Pi ⓘ",
            "State ⓘ", "Source",
        ], f"unexpected header row: {labels!r}"
```

And update `test_slug_header_is_uppercase` to allow the glyph:

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
        assert labels[0] == "SKILL ⓘ", f"slug header: {labels[0]!r}"
```

- [ ] **Step 2: Run tests to confirm the failures**

Run: `uv run pytest tests/test_tui/test_skill_grid_column_info.py -v`
Expected: FAIL — Claude Code / Pi / SKILL labels don't yet contain `ⓘ`.

- [ ] **Step 3: Update `_rebuild` to glyph every non-Source column**

Open `src/agent_toolkit_tui/widgets/skill_grid.py`. Replace the
`def _rebuild(self, table: DataTable)` column-header section. Currently:

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
        table.add_column("Source", width=30)
```

becomes:

```python
    def _rebuild(self, table: DataTable) -> None:
        saved = table.cursor_coordinate
        table.clear(columns=True)
        # Slug column has cell-info (the slug-cell panel) → glyph it.
        table.add_column(f"SKILL {_INFO_GLYPH}", width=20)
        for agent in INTERACTIVE_AGENTS:
            # Every interactive agent column exposes either a column-info
            # modal (Universal) or per-cell info (Claude Code, Pi via
            # CellInfoScreen) — glyph them all.
            base = "Universal" if agent == "universal" else AGENTS[agent].display_name
            table.add_column(f"{base} {_INFO_GLYPH}", width=14)
        # State has a column-info modal → glyph it.
        table.add_column(f"State {_INFO_GLYPH}", width=10)
        # Source is passive — no info panel, no glyph.
        table.add_column("Source", width=30)
```

- [ ] **Step 4: Run the header tests**

Run: `uv run pytest tests/test_tui/test_skill_grid_column_info.py -v`
Expected: All PASS.

- [ ] **Step 5: Run the full TUI test module to confirm nothing else asserts on old labels**

Run: `uv run pytest tests/test_tui/ -v`
Expected: All PASS. If any other test asserts on the old "Claude Code" / "Pi" /
"SKILL" labels, update those assertions to the new strings ("Claude Code ⓘ" /
"Pi ⓘ" / "SKILL ⓘ"). (Search before running: `grep -rn '"Claude Code"\|"Pi"\|"SKILL"' tests/test_tui/`. As of the spec, only the three tests touched in step 1 hold these labels.)

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py tests/test_tui/test_skill_grid_column_info.py
git commit -m "fix(tui): show ⓘ glyph on every column whose cells expose an info panel (#212)"
```

---

## Task 5: Em-dash for `library` state in slug-cell modal

**Files:**
- Test: `tests/test_tui/test_cell_info.py` (extend)
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py` (`action_info` slug-column branch)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tui/test_cell_info.py`:

```python
@pytest.mark.asyncio
async def test_info_on_slug_column_library_state_renders_em_dash():
    """A row in the 'library' state shows `State:  —` (em dash), not the literal word (#212)."""
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    # Build a row with state='library' — _row() defaults to 'clean', so override.
    row = _row("journal")
    row.state = "library"

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        t = g.query_one("#skill-table", DataTable)
        t.cursor_coordinate = Coordinate(row=0, column=0)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen)
        body = str(a.screen.query_one("#cell-info-body").content)
        assert "State:  —" in body, f"expected em-dash for library state, got: {body!r}"
        assert "State:  library" not in body, (
            f"slug-cell modal should not print literal 'library', got: {body!r}"
        )


@pytest.mark.asyncio
async def test_info_on_slug_column_non_library_state_still_renders_word():
    """A non-library state still shows the literal state value (e.g. 'clean')."""
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    row = _row("journal")  # state defaults to 'clean'

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        t = g.query_one("#skill-table", DataTable)
        t.cursor_coordinate = Coordinate(row=0, column=0)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen)
        body = str(a.screen.query_one("#cell-info-body").content)
        assert "State:  clean" in body, f"non-library state should render literal: {body!r}"
```

Note: `_row()` in `test_cell_info.py` returns a frozen `SkillRow` — but
`SkillRow` is `@dataclass` (not frozen), so `row.state = "library"` is
allowed. Verify against the import at the top of the file (it already imports
SkillRow). If the dataclass is frozen, switch to constructing the row by
calling `SkillRow(...)` directly.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_cell_info.py::test_info_on_slug_column_library_state_renders_em_dash -v`
Expected: FAIL — body contains "State:  library".

- [ ] **Step 3: Substitute em-dash in the slug-column body**

Open `src/agent_toolkit_tui/widgets/skill_grid.py`. In `action_info`, find the
slug-column branch (current code around line 169-178):

```python
        # Slug column → source/ref/state context.
        if coord.column == 0:
            title = f"{row.slug} · slug"
            body = (
                f"Skill [b]{row.slug}[/]\n"
                f"Source: {row.source}\n"
                f"Ref:    {row.ref}\n"
                f"State:  {row.state}"
            )
            if row.description:
                body += f"\n\nDescription:\n{row.description}"
```

replace with:

```python
        # Slug column → source/ref/state context.
        if coord.column == 0:
            # 'library' = no meaningful state (slug in library, not yet
            # installed here). Render as em-dash so the modal doesn't look
            # like it's printing a debug literal.
            state_display = "—" if row.state == "library" else row.state
            title = f"{row.slug} · slug"
            body = (
                f"Skill [b]{row.slug}[/]\n"
                f"Source: {row.source}\n"
                f"Ref:    {row.ref}\n"
                f"State:  {state_display}"
            )
            if row.description:
                body += f"\n\nDescription:\n{row.description}"
```

- [ ] **Step 4: Run the new tests**

Run: `uv run pytest tests/test_tui/test_cell_info.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py tests/test_tui/test_cell_info.py
git commit -m "fix(tui): render slug-cell State as em-dash for 'library' rows (#212)"
```

---

## Task 6: Full suite + manual smoke

**Files:** (no edits — verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `uv run pytest -q`
Expected: PASS. Same skip count as baseline (`317 passed, 2 skipped` or higher
counts after the new tests).

- [ ] **Step 2: Run lefthook pre-commit hook to mirror CI**

Run: `uv run pytest -q` (lefthook runs this on commit; already exercised by
each Task's commit step — this is a final belt-and-braces check).
Expected: PASS.

- [ ] **Step 3: Log full-suite result for the PR**

Append the count to `assets/verification/212/flow.log` so the PR body can
reference it:

```bash
echo "[$(date '+%H:%M:%S')] full suite: $(uv run pytest -q --tb=no 2>&1 | tail -1)" >> assets/verification/212/flow.log
```

---

## Self-review

**Spec coverage**:
- Fix 1 (description) → Task 1.
- Fix 2 (marker gating) → Tasks 2 + 3.
- Fix 3 (glyph coverage) → Task 4.
- Fix 4 (em-dash state) → Task 5.
- Full-suite confirmation → Task 6.

**Placeholder scan**: no TBDs, no "similar to Task N", every code step has the actual code.

**Type/name consistency**:
- `get_column_info(name, *, context=None)` — declared in Task 2, used in Task 3.
- `_context_for(*, key, row_index)` — declared in Task 3, no other callers.
- `library_skill_path` — already exists in `skill_paths.py` (line 98).
- `state_display` — local var, scoped to the slug-column branch.
