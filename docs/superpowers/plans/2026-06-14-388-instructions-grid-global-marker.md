# 🌐 Global Marker on the Instructions Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the 🌐 globe marker on the TUI instructions grid in project scope when a harness slot is also linked at global scope, matching the skills/agents/pi grids.

**Architecture:** Pure parity-port of the agents-tab marker (#374). Three layers: (1) `instruction_state.build_instruction_rows` probes the `(harness, "global")` shadow cell at project scope; (2) `instruction_grid._cell_glyph` appends ` 🌐` when that shadow cell is linked; (3) `column_info` + `instruction_grid._context_for` extend the existing 🌐 explainer block to instructions. Display-only — no install/uninstall/precedence change.

**Tech Stack:** Python, Textual (DataTable TUI), pytest + pytest-asyncio. Existing test patterns in `tests/test_tui/test_agent_grid_global_indicator.py` and `tests/test_tui/test_instruction_state.py`.

---

## Background the worker needs

- The instructions grid renders exactly two interactive harnesses, derived from
  `instructions_nonstandard_main()`: `claude-code` and `gemini-cli`. Tests must
  index `INTERACTIVE_HARNESSES[i]`, never hard-code names (the tuple is derived).
- `InstructionCell` has two fields: `linked: bool` and `conflict: bool` (no
  drift/stray/skipped). So `linked` is the whole marker gate — simpler than
  `SkillCell`, identical to `AgentCell`'s gate.
- Cell key shape is `(harness_name, scope)` — e.g. `("claude-code", "project")`
  and the shadow `("claude-code", "global")`.
- The reference implementation is the agents tab. Read these before starting:
  - `src/agent_toolkit_tui/agent_state.py:121-135` (the global shadow probe)
  - `src/agent_toolkit_tui/widgets/agent_grid.py:408-417` (the `_cell_glyph` marker branch)
  - `src/agent_toolkit_tui/widgets/agent_grid.py:331-341` (the row-aware `_context_for`)
  - `src/agent_toolkit_tui/column_info.py:44-66` (the `show_marker` gate + `indicator_note`)
  - `tests/test_tui/test_agent_grid_global_indicator.py` (the render-test shape to mirror)

## File Structure

- **Modify** `src/agent_toolkit_tui/instruction_state.py` — add the
  `(harness, "global")` shadow-cell probe in both row-construction branches.
- **Modify** `src/agent_toolkit_tui/widgets/instruction_grid.py` — add
  `_GLOBAL_GLYPH`, the `_cell_glyph` marker branch, and make `_context_for`
  row-aware so the standard-column info panel reports `global_linked`.
- **Modify** `src/agent_toolkit_tui/column_info.py` — extend `show_marker` to
  include `"instructions"`, add instructions copy, correct the stale comment.
- **Create** `tests/test_tui/test_instruction_grid_global_indicator.py` — render
  tests mirroring the agents-tab indicator tests.
- **Modify** `tests/test_tui/test_instruction_state.py` — add shadow-cell probe
  tests.
- **Modify** `tests/test_tui/test_column_info.py` — **invert** the two existing
  tests that codify the old #374 instructions-exclusion
  (`test_standard_info_is_asset_type_aware`,
  `test_standard_info_instructions_never_shows_marker`); they assert no marker
  for instructions and the gate change makes them fail (Task 4 step 3d). This is
  the one place the parity-port touches pre-existing tests rather than adding.

---

## Task 1: State layer — global shadow-cell probe (locked-entry branch)

**Files:**
- Modify: `src/agent_toolkit_tui/instruction_state.py:168-186`
- Test: `tests/test_tui/test_instruction_state.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_tui/test_instruction_state.py`. The global canonical resolves
via `instructions_paths.library_root` (`global_canonical_agents_md()` returns
`library_root().parent / "AGENTS.md"`), so the test isolates it by
monkeypatching `library_root` to a path under `tmp_path` — the exact pattern the
existing `test_build_instruction_rows_*` tests use. The global claude-code
pointer (`~/.claude/CLAUDE.md`) resolves via the passed `home`. The lock entry
class is `InstructionsLockEntry(scope, source, harnesses=[])` (see
`instructions_lock.py:38`).

```python
def test_project_scope_probes_global_shadow_cell(tmp_path: Path, monkeypatch):
    """At project scope, build_instruction_rows probes (harness, 'global') for
    each row when home is set, mirroring agent_state (#374). The global pointer
    being linked surfaces as a (harness, 'global') cell with linked=True."""
    from agent_toolkit_cli import instructions_paths

    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "proj"
    project.mkdir()

    # Isolate the global canonical under tmp_path (mirrors the existing
    # test_build_instruction_rows_* tests). The global canonical is then
    # <agent_toolkit_dir>/AGENTS.md.
    agent_toolkit_dir = home / ".agent-toolkit"
    agent_toolkit_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: agent_toolkit_dir / "instructions",
    )
    glob_canonical = agent_toolkit_dir / "AGENTS.md"
    glob_canonical.write_text("# global AGENTS\n")

    # Project canonical so the locked row's project cells resolve.
    proj_canonical = instructions_paths.project_canonical_agents_md(project)
    proj_canonical.write_text("# project AGENTS\n")

    # Project lock entry → locked-entry branch.
    lock_file = instructions_paths.project_lock_path(project)
    lock_file.write_text(
        '{"version": 1, "instructions": {"AGENTS.md": '
        '{"scope": "project", "source": "AGENTS.md", "harnesses": ["claude-code"]}}}\n'
    )

    # Install the GLOBAL claude-code pointer (~/.claude/CLAUDE.md → global canonical).
    from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
    glob_pointer = _pointer_path("claude-code", "global", None, home)
    glob_pointer.parent.mkdir(parents=True, exist_ok=True)
    glob_pointer.symlink_to(glob_canonical)

    rows = build_instruction_rows(scope="project", home=home, project=project)
    assert rows, "expected one AGENTS.md row"
    global_cell = rows[0].cells.get(("claude-code", "global"))
    assert global_cell is not None
    assert global_cell.linked is True
```

> Confirm `_pointer_path("claude-code", "global", None, home)` resolves to
> `<home>/.claude/CLAUDE.md` (it should — the existing
> `test_build_instruction_rows_with_lock_entry` builds that exact pointer by
> hand at `<home>/.claude/CLAUDE.md`).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_instruction_state.py::test_project_scope_probes_global_shadow_cell -v`
Expected: FAIL — `global_cell is None` (the shadow probe does not exist yet).

- [ ] **Step 3: Write minimal implementation**

In `build_instruction_rows`, the locked-entry branch (currently L168-186),
after building the per-scope `cells` for each row, add the global probe. Replace
the loop body so each row also probes global at project scope:

```python
    # Lock has entries — build one row per slug.
    rows: list[InstructionRow] = []
    for slug in sorted(lock.instructions):
        entry = lock.instructions[slug]
        cells: dict[tuple[str, str], InstructionCell] = {}
        for harness in INTERACTIVE_HARNESSES:
            cell = _cell_for(
                slug, harness,
                scope=scope, home=home, project=project,
                _canonical=canonical,
            )
            if cell is not None:
                cells[(harness, scope)] = cell
        # In project scope, also probe global so the grid can render the
        # globally-linked 🌐 indicator (#388, mirrors agent_state.py:131-135).
        # Skipped when home is None. The global probe resolves the GLOBAL
        # canonical itself (scope="global"), so do NOT pass the project
        # _canonical override here.
        if scope == "project" and home is not None:
            for harness in INTERACTIVE_HARNESSES:
                gcell = _cell_for(
                    slug, harness,
                    scope="global", home=home, project=None,
                )
                if gcell is not None:
                    cells[(harness, "global")] = gcell
        rows.append(InstructionRow(
            slug=slug,
            source=entry.source,
            canonical_exists=canonical_exists,
            cells=cells,
        ))
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_instruction_state.py::test_project_scope_probes_global_shadow_cell -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui/test_instruction_state.py src/agent_toolkit_tui/instruction_state.py
git commit -m "feat(tui): probe global shadow cell for instruction rows (locked branch, #388)"
```

---

## Task 2: State layer — global shadow-cell probe (empty-lock fresh-user branch)

**Files:**
- Modify: `src/agent_toolkit_tui/instruction_state.py:148-166`
- Test: `tests/test_tui/test_instruction_state.py`

- [ ] **Step 1: Write the failing test**

```python
def test_empty_lock_fresh_user_row_probes_global_shadow_cell(tmp_path: Path, monkeypatch):
    """The empty-lock fresh-user row (canonical exists, no lock entries) also
    gets the (harness, 'global') shadow cell at project scope (#388)."""
    from agent_toolkit_cli import instructions_paths

    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "proj"
    project.mkdir()

    agent_toolkit_dir = home / ".agent-toolkit"
    agent_toolkit_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: agent_toolkit_dir / "instructions",
    )
    glob_canonical = agent_toolkit_dir / "AGENTS.md"
    glob_canonical.write_text("# global AGENTS\n")

    # Project canonical exists but NO project lock entries → fresh-user branch.
    proj_canonical = instructions_paths.project_canonical_agents_md(project)
    proj_canonical.write_text("# project AGENTS\n")

    # Global claude-code pointer linked.
    from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
    glob_pointer = _pointer_path("claude-code", "global", None, home)
    glob_pointer.parent.mkdir(parents=True, exist_ok=True)
    glob_pointer.symlink_to(glob_canonical)

    rows = build_instruction_rows(scope="project", home=home, project=project)
    assert rows and rows[0].slug == "AGENTS.md"
    gcell = rows[0].cells.get(("claude-code", "global"))
    assert gcell is not None and gcell.linked is True
```

> The project lock must be ABSENT for this branch — `project_lock_path(project)`
> resolves to `<project>/instructions-lock.json`, which the test never writes,
> so `read_lock` returns an empty lock and the fresh-user branch fires.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_instruction_state.py::test_empty_lock_fresh_user_row_probes_global_shadow_cell -v`
Expected: FAIL — `gcell is None`.

- [ ] **Step 3: Write minimal implementation**

In the empty-lock branch (currently L152-166), after the per-scope cell loop,
add the same global probe:

```python
        row = InstructionRow(
            slug="AGENTS.md",
            source="AGENTS.md",
            canonical_exists=True,
            cells={},
        )
        for harness in INTERACTIVE_HARNESSES:
            cell = _cell_for(
                "AGENTS.md", harness,
                scope=scope, home=home, project=project,
                _canonical=canonical,
            )
            if cell is not None:
                row.cells[(harness, scope)] = cell
        # Project-scope global shadow probe for the 🌐 marker (#388).
        if scope == "project" and home is not None:
            for harness in INTERACTIVE_HARNESSES:
                gcell = _cell_for(
                    "AGENTS.md", harness,
                    scope="global", home=home, project=None,
                )
                if gcell is not None:
                    row.cells[(harness, "global")] = gcell
        return [row]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_instruction_state.py::test_empty_lock_fresh_user_row_probes_global_shadow_cell -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui/test_instruction_state.py src/agent_toolkit_tui/instruction_state.py
git commit -m "feat(tui): probe global shadow cell for empty-lock instruction row (#388)"
```

---

## Task 3: Grid layer — 🌐 marker in `_cell_glyph`

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/instruction_grid.py:33-39` (constants) and `:409-421` (`_cell_glyph`)
- Test: `tests/test_tui/test_instruction_grid_global_indicator.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tui/test_instruction_grid_global_indicator.py`, mirroring
`test_agent_grid_global_indicator.py`:

```python
"""Render tests for the instructions-tab globally-linked indicator (#388).

Mirrors test_agent_grid_global_indicator.py (#374). Harness names are derived
(INTERACTIVE_HARNESSES), so tests index into the tuple instead of hard-coding.
"""
from __future__ import annotations

import pytest
from rich.text import Text
from textual.app import App
from textual.widgets import DataTable

from agent_toolkit_tui.instruction_state import (
    INTERACTIVE_HARNESSES,
    InstructionCell,
    InstructionRow,
)
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid

_H0 = INTERACTIVE_HARNESSES[0]  # claude-code
_H1 = INTERACTIVE_HARNESSES[1]  # gemini-cli


def _row_with(
    *,
    project_cells: dict[str, InstructionCell] | None = None,
    global_cells: dict[str, InstructionCell] | None = None,
) -> InstructionRow:
    cells: dict[tuple[str, str], InstructionCell] = {}
    for harness, cell in (project_cells or {}).items():
        cells[(harness, "project")] = cell
    for harness, cell in (global_cells or {}).items():
        cells[(harness, "global")] = cell
    return InstructionRow(
        slug="AGENTS.md", source="AGENTS.md", canonical_exists=True, cells=cells,
    )


async def _rendered_plain(app: App, pilot, harness: str) -> str:
    table = app.query_one("#instruction-table", DataTable)
    grid = app.query_one("#g", InstructionGrid)
    grid._rebuild(table)  # type: ignore[attr-defined]
    await pilot.pause()
    row_key = list(table.rows.keys())[0]
    # Column layout: 0=slug, 1=standard, 2.. = harness cols (in
    # INTERACTIVE_HARNESSES order), last = Source.
    col_index = 2 + list(INTERACTIVE_HARNESSES).index(harness)
    col_key = list(table.columns.keys())[col_index]
    return Text.from_markup(str(table.get_cell(row_key, col_key))).plain


@pytest.mark.asyncio
async def test_project_scope_globally_linked_cell_shows_marker():
    row = _row_with(
        project_cells={h: InstructionCell(linked=False, conflict=False)
                       for h in INTERACTIVE_HARNESSES},
        global_cells={_H0: InstructionCell(linked=True, conflict=False),
                      _H1: InstructionCell(linked=False, conflict=False)},
    )

    class _A(App):
        def compose(self):
            yield InstructionGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", InstructionGrid).set_scope("project")
        await pilot.pause()
        assert "🌐" in await _rendered_plain(a, pilot, _H0)
        assert "🌐" not in await _rendered_plain(a, pilot, _H1)


@pytest.mark.asyncio
async def test_global_scope_view_does_not_show_marker():
    row = _row_with(
        global_cells={h: InstructionCell(linked=True, conflict=False)
                      for h in INTERACTIVE_HARNESSES},
    )

    class _A(App):
        def compose(self):
            yield InstructionGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", InstructionGrid).set_scope("global")
        await pilot.pause()
        for harness in INTERACTIVE_HARNESSES:
            assert "🌐" not in await _rendered_plain(a, pilot, harness)


@pytest.mark.asyncio
async def test_not_applicable_project_cell_still_shows_marker():
    """No project cell (em-dash base) but a linked global cell → marker appends
    to the em-dash, matching agents/skills."""
    row = _row_with(
        project_cells={},
        global_cells={_H0: InstructionCell(linked=True, conflict=False)},
    )

    class _A(App):
        def compose(self):
            yield InstructionGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", InstructionGrid).set_scope("project")
        await pilot.pause()
        plain = await _rendered_plain(a, pilot, _H0)
        assert "—" in plain and "🌐" in plain


@pytest.mark.asyncio
async def test_conflict_cell_still_shows_marker():
    """A conflict project cell ([red]![/] base) with a linked global cell still
    appends the marker (the marker is independent of the base glyph)."""
    row = _row_with(
        project_cells={_H0: InstructionCell(linked=False, conflict=True)},
        global_cells={_H0: InstructionCell(linked=True, conflict=False)},
    )

    class _A(App):
        def compose(self):
            yield InstructionGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", InstructionGrid).set_scope("project")
        await pilot.pause()
        assert "🌐" in await _rendered_plain(a, pilot, _H0)


@pytest.mark.asyncio
async def test_no_global_cells_no_marker_no_crash():
    """Rows without any (harness, 'global') cells render no marker, no crash."""
    row = _row_with(
        project_cells={h: InstructionCell(linked=True, conflict=False)
                       for h in INTERACTIVE_HARNESSES},
    )

    class _A(App):
        def compose(self):
            yield InstructionGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", InstructionGrid).set_scope("project")
        await pilot.pause()
        for harness in INTERACTIVE_HARNESSES:
            assert "🌐" not in await _rendered_plain(a, pilot, harness)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_instruction_grid_global_indicator.py -v`
Expected: FAIL — markers absent (`🌐` not appended).

- [ ] **Step 3: Write minimal implementation**

Add the constant alongside the others in `instruction_grid.py` (after L39):

```python
_GLOBAL_GLYPH    = "🌐"
```

Replace `_cell_glyph` (L409-421) with the marker-appending version:

```python
    def _cell_glyph(self, *, row: InstructionRow, harness: str) -> str:
        """Return the display glyph for a harness cell. Never named _render_*."""
        cell = row.cells.get((harness, self._scope))
        if cell is None:
            base = _NOT_AVAIL_GLYPH
        elif cell.conflict:
            base = _CONFLICT_GLYPH
        else:
            pending = self._pending.get((self._scope, harness, row.slug))
            if pending == "link":
                base = _PENDING_LINK
            elif pending == "unlink":
                base = _PENDING_UNLINK
            else:
                base = _LINKED_GLYPH if cell.linked else _UNLINKED_GLYPH
        # In project scope, mark cells whose harness slot is also linked
        # globally — same indicator as skills/agents/pi (#388). InstructionCell
        # has no drift/stray/skipped, so linked is the whole gate. Appends to
        # any base, including the not-applicable em-dash and the conflict glyph.
        if self._scope == "project":
            global_cell = row.cells.get((harness, "global"))
            if global_cell is not None and global_cell.linked:
                return f"{base} {_GLOBAL_GLYPH}"
        return base
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_instruction_grid_global_indicator.py -v`
Expected: PASS (all five).

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui/test_instruction_grid_global_indicator.py src/agent_toolkit_tui/widgets/instruction_grid.py
git commit -m "feat(tui): render 🌐 marker on project-scope instruction cells (#388)"
```

---

## Task 4: Info panel — extend the 🌐 block to instructions

**Files:**
- Modify: `src/agent_toolkit_tui/column_info.py:44-66`
- Modify: `src/agent_toolkit_tui/widgets/instruction_grid.py:341-352` (`_context_for`) and `:169-173` (call site)
- Test: `tests/test_tui/test_instruction_grid_global_indicator.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tui/test_instruction_grid_global_indicator.py`:

```python
@pytest.mark.asyncio
async def test_context_for_standard_reports_global_linked_true():
    """The standard-key context surfaces whether the focused row's slot is
    linked globally, mirroring agent_grid._context_for (#388)."""
    row = _row_with(
        project_cells={_H0: InstructionCell(linked=False, conflict=False)},
        global_cells={_H0: InstructionCell(linked=True, conflict=False)},
    )

    class _A(App):
        def compose(self):
            yield InstructionGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", InstructionGrid)
        g.set_scope("project")
        await pilot.pause()
        ctx = g._context_for(key="standard", row_index=0)  # type: ignore[attr-defined]
        assert ctx is not None
        assert ctx["asset_type"] == "instructions"
        assert ctx["global_linked"] is True


@pytest.mark.asyncio
async def test_context_for_standard_reports_global_linked_false():
    """No global cell (or out-of-range row) → global_linked False, no crash."""
    row = _row_with(
        project_cells={_H0: InstructionCell(linked=True, conflict=False)},
    )

    class _A(App):
        def compose(self):
            yield InstructionGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", InstructionGrid)
        g.set_scope("project")
        await pilot.pause()
        ctx = g._context_for(key="standard", row_index=0)  # type: ignore[attr-defined]
        assert ctx is not None and ctx["global_linked"] is False
        oob = g._context_for(key="standard", row_index=99)  # type: ignore[attr-defined]
        assert oob is not None and oob["global_linked"] is False


def test_column_info_instructions_marker_block_present():
    """column_info renders the 🌐 marker block for instructions when the focused
    row is globally linked (#388)."""
    from agent_toolkit_tui.column_info import get_column_info

    info = get_column_info(
        "standard",
        context={"asset_type": "instructions", "names": (), "global_linked": True},
    )
    assert info is not None
    assert any("🌐 marker" in line for line in info.lines)


def test_column_info_instructions_marker_block_omitted_when_not_global():
    """Block omitted when the focused row is not globally linked."""
    from agent_toolkit_tui.column_info import get_column_info

    info = get_column_info(
        "standard",
        context={"asset_type": "instructions", "names": (), "global_linked": False},
    )
    assert info is not None
    assert not any("🌐 marker" in line for line in info.lines)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_instruction_grid_global_indicator.py -k "context_for or marker_block" -v`
Expected: FAIL — `_context_for` rejects the `row_index` kwarg / returns no
`global_linked`; the column-info block is gated to skills/agents only.

- [ ] **Step 3: Write minimal implementation**

**3a.** In `column_info.py`, extend the gate and add instructions copy, and fix
the comment (L41-66):

```python
    # The 🌐 marker block applies to the asset types whose grids render the
    # marker: skills (#188), agents (#374), and instructions (#388). It is
    # contextual — it only makes sense when the focused row IS linked at global
    # scope, so omit it when the caller says otherwise. (Earlier the block was
    # gated to skills/agents because instructions were thought to have no
    # cross-scope signal; in fact claude-code and gemini-cli both MERGE the
    # global and project instruction files, so "also linked globally" is a true
    # signal here too — see the #388 spec.)
    show_marker = asset_type in ("skills", "agents", "instructions") and (
        context is None or bool(ctx.get("global_linked", True))
    )
    indicator_note: list[str] = []
    if show_marker:
        indicator_note = ["", "🌐 marker (project scope only):"]
        if asset_type == "skills":
            indicator_note += [
                "  This skill is also installed globally,",
                "  so you may not need it at project scope too.",
            ]
        elif asset_type == "instructions":
            # Instructions copy actively RETRACTS the skills "you may not need
            # it" redundancy reading: claude-code and gemini-cli MERGE the
            # global + project memory files, so the global AGENTS.md is added
            # to (not replaced by) the project one — the project pointer is
            # never redundant (#388, adversarial-review finding).
            indicator_note += [
                "  This harness also loads a global AGENTS.md,",
                "  merged with (not replaced by) the project one.",
            ]
        else:
            # Agents copy stays presence-neutral (#374): per-harness
            # project-vs-global precedence is not asserted.
            indicator_note += ["  This agent is also installed globally."]
```

Also update the `title=` ternary so instructions gets a sensible title — the
standard column for instructions is a canonical-status column, not a bundle:

```python
        title=(
            "Standard slot (agents)" if asset_type == "agents"
            else "Standard projection (.mcp.json)" if asset_type == "mcps"
            else "Standard canonical (AGENTS.md)" if asset_type == "instructions"
            else "Standard bundle"
        ),
```

Finally, fix the `get_column_info` **docstring** (currently L109-112) — it lists
`global_linked (skills/agents 🌐 marker block)`. Left stale, a future developer
reads "skills/agents" and re-gates instructions out, repeating the #374 mistake
this work corrects (design-lens finding). Change that line to:

```python
    `extra_lines` (caller-supplied trailing lines, e.g. the agents
    panel's devin note), and `global_linked` (skills/agents/instructions 🌐
    marker block).
```

**3b.** In `instruction_grid.py`, make `_context_for` row-aware (mirror
`agent_grid._context_for`). Replace the current signature `_context_for(self, *, key)`
and body (L341-352):

```python
    def _context_for(self, *, key: str, row_index: int | None = None) -> dict | None:
        """Context for get_column_info(). The standard panel enumerates the
        native AGENTS.md readers from the harness-matrix SSOT (#351) and, when
        a row is focused, reports whether that row's slot is linked globally so
        the 🌐 marker block renders (#388, mirrors agent_grid._context_for)."""
        if key == "standard":
            from agent_toolkit_cli.instructions_matrix import instructions_matrix_rows

            native = tuple(
                r["harness"] for r in instructions_matrix_rows()
                if r["verdict"] == "native"
            )
            global_linked = False
            if row_index is not None and 0 <= row_index < len(self._rows):
                row = self._rows[row_index]
                global_linked = any(
                    cell.linked
                    for (harness, scope), cell in row.cells.items()
                    if scope == "global"
                )
            return {
                "asset_type": "instructions",
                "names": native,
                "global_linked": global_linked,
            }
        return None
```

**3c.** Update the `_context_for` call site in `action_info` (L169-171) to pass
the focused row index:

```python
        key = self._column_key_for_index(coord.column)
        if key is not None:
            info = get_column_info(
                key, context=self._context_for(key=key, row_index=coord.row)
            )
            if info is not None:
                self.app.push_screen(ColumnInfoModal(info))
                return
```

**3d. Invert the two pre-existing tests that codify the OLD #374 exclusion**
(coherence + feasibility finding, anchor 100 — without this Task 5 breaks). Two
tests in `tests/test_tui/test_column_info.py` assert the marker is excluded for
instructions; the gate change at 3a makes both fail. Update them:

`test_standard_info_is_asset_type_aware` (L116-128) passes
`{asset_type: "instructions", names: (...)}` with NO `global_linked`, so the new
gate's `ctx.get("global_linked", True)` default fires the block. Add
`global_linked=False` to keep this test's intent (it checks names/title, not the
marker) and keep its no-marker assertion valid:

```python
def test_standard_info_is_asset_type_aware():
    """The factory takes the names (and asset type) from context so the instruction
    grid can reuse the same registry key (#351)."""
    info = get_column_info(
        "standard",
        context={
            "asset_type": "instructions",
            "names": ("alpha-harness", "beta-harness"),
            "global_linked": False,
        },
    )
    text = " ".join(info.lines)
    assert "instructions" in text and "(2)" in text
    assert "alpha-harness" in text and "beta-harness" in text
    # Marker omitted here because this row is NOT globally linked (#388).
    assert "🌐" not in text
```

`test_standard_info_instructions_never_shows_marker` (L150-157) asserts the OLD
"excluded by design" behavior and is now wrong. Replace it with an
instructions-shows-marker test mirroring the agents one:

```python
def test_standard_info_instructions_shows_marker_when_globally_linked():
    """#388: instructions now gets the 🌐 explainer when the focused row IS
    globally linked, with merge-accurate copy (reverses the #374 exclusion)."""
    info = get_column_info(
        "standard", context={"asset_type": "instructions", "global_linked": True},
    )
    joined = "\n".join(info.lines)
    assert "🌐" in joined
    assert "merged with (not replaced by)" in joined


def test_standard_info_instructions_omits_marker_when_not_globally_linked():
    """No marker when the instructions row is not globally linked."""
    info = get_column_info(
        "standard", context={"asset_type": "instructions", "global_linked": False},
    )
    assert "🌐" not in "\n".join(info.lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_instruction_grid_global_indicator.py -k "context_for or marker_block" tests/test_tui/test_column_info.py -v`
Expected: PASS — including the two updated `test_column_info.py` tests. If
either updated test still fails, the gate or copy is wrong.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/column_info.py src/agent_toolkit_tui/widgets/instruction_grid.py tests/test_tui/test_instruction_grid_global_indicator.py tests/test_tui/test_column_info.py
git commit -m "feat(tui): surface global-linked state in instruction column-info panel (#388)"
```

---

## Task 5: Regression sweep — full suite + lint/type

**Files:** none (verification only)

- [ ] **Step 1: Run the full TUI + column-info test surface**

Run: `uv run pytest tests/test_tui/ -q`
Expected: all pass — INCLUDING the two `test_column_info.py` tests inverted in
Task 4 step 3d. If `test_standard_info_is_asset_type_aware` or the old
`test_standard_info_instructions_never_shows_marker` is still red, step 3d was
not applied. The two known HOME-isolation env failures
(`test_empty_machine_is_empty`,
`test_build_instruction_rows_empty_lock_no_canonical`) are pre-existing and
unrelated; confirm they were already failing on the base before claiming green.

- [ ] **Step 2: Run the full suite**

Run: `uv run pytest -q`
Expected: same green/whitelisted-fail count as the base. If a new failure
appears, it is yours to fix.

- [ ] **Step 3: Lint + type check the changed files**

Run: `uv run ruff check src/agent_toolkit_tui/ tests/test_tui/ && uv run mypy src/agent_toolkit_tui/instruction_state.py src/agent_toolkit_tui/widgets/instruction_grid.py src/agent_toolkit_tui/column_info.py`
Expected: no NEW ruff/mypy errors relative to the base (the repo has known
pre-existing mypy noise; compare counts, don't assume zero).

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "test(tui): regression sweep for instructions 🌐 marker (#388)"
```

---

## Self-Review (run by the plan author)

**1. Spec coverage:**
- AC1 (project-scope linked cell renders 🌐, global scope none) → Task 3 tests
  `test_project_scope_globally_linked_cell_shows_marker`,
  `test_global_scope_view_does_not_show_marker`. ✓
- AC2 (shadow cell in BOTH branches, gated on home) → Tasks 1 + 2. ✓
- AC3 (panel surfaces global-linked) → Task 4 `_context_for` + column-info tests. ✓
- AC4 (`show_marker` includes instructions + comment corrected) → Task 4 step 3a
  (gate + comment + docstring) and step 3d (invert the two pre-existing
  exclusion tests). ✓
- AC5 (global scope unchanged, existing tests green) → Task 3
  `test_global_scope_view_does_not_show_marker` + Task 5 sweep. ✓

**2. Placeholder scan:** The Task 1/2 state tests use a raw JSON lock-file write
(no entry-constructor placeholder) and the real `library_root` monkeypatch seam
— verified against the existing `test_build_instruction_rows_*` tests. No
placeholders remain.

**3. Type consistency:** `InstructionCell(linked=..., conflict=...)` used
consistently (two fields, both required). `_context_for(key=..., row_index=...)`
signature matches the call-site change in Task 4 step 3c (`row_index` is
optional here, vs required in `agent_grid._context_for` — a deliberate
divergence so the single call site is the only one that must change; the lock
entry class is `InstructionsLockEntry`, not `InstructionEntry`). `InstructionRow`
constructor (`slug`, `source`, `canonical_exists`, `cells`) matches usage.

**4. Critical-review findings (ce-doc-review, M):** the must-fix
break-of-existing-tests finding is resolved by Task 4 step 3d; the stale-docstring
and 🌐-redundancy-connotation findings are resolved in step 3a (docstring update
+ "merged with, not replaced by" copy). Two advisory findings waived: the
premise's version-dependence on external harness behavior (noted as a spec
residual risk) and the harness-cell CellInfoScreen omitting global state (explicit
parity with agents — out of scope, follow-up if desired).
