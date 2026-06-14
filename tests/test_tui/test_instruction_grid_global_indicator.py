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
