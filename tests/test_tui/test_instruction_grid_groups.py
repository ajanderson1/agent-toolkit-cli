"""Standard / Non-standard column groups on the instruction grid (#351).

Mirrors test_skill_grid_groups.py with the instructions composition:
standard read-only column tagged STANDARD; claude-code + gemini-cli +
`… +N ⓘ` tagged NON-STD; expand shows the remaining symlink harnesses as
installable columns; per-grid session state independent of the skill grid.
"""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.composition import (
    instructions_longtail,
    instructions_nonstandard_big_five,
    skills_longtail,
    skills_nonstandard_big_five,
)
from agent_toolkit_tui.instruction_state import InstructionCell, InstructionRow
from agent_toolkit_tui.skill_state import SkillCell, SkillRow
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _full_row(slug: str = "AGENTS.md", *, scope: str = "global") -> InstructionRow:
    """Row with cells for the FULL composition — tail toggles bail on
    cell=None, so tail cells must exist (#351 fixture note)."""
    harnesses = instructions_nonstandard_big_five() + instructions_longtail()
    cells = {
        (h, scope): InstructionCell(linked=False, conflict=False)
        for h in harnesses
    }
    return InstructionRow(
        slug=slug, source="AGENTS.md", canonical_exists=True, cells=cells,
    )


class _GridApp(App):
    def compose(self) -> ComposeResult:
        yield InstructionGrid([_full_row()], id="g")


def _labels(table: DataTable) -> list[str]:
    return [str(c.label) for c in table.columns.values()]


def _pseudo_column_index(grid: InstructionGrid) -> int:
    # Layout: [0]=slug, [1]=standard, [2..2+N-1]=active harnesses, [2+N]=pseudo.
    return 2 + len(grid._active_harnesses())


def _cursor_to_pseudo(grid: InstructionGrid, table: DataTable, *, row: int = 0) -> None:
    table.cursor_coordinate = Coordinate(row=row, column=_pseudo_column_index(grid))
    table.focus()


@pytest.mark.asyncio
async def test_default_columns_collapsed():
    app = _GridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#instruction-table", DataTable)
        labels = _labels(table)
        # slug + standard + claude-code + gemini-cli + pseudo + source
        assert any("standard" in l for l in labels)
        assert any("CLAUDE.md" in l for l in labels)
        assert any("GEMINI.md" in l for l in labels)
        assert any(f"… +{len(instructions_longtail())}" in l for l in labels)
        assert not any("augment" in l for l in labels)        # tail collapsed
        assert sum("STANDARD" in l for l in labels) == 1
        assert sum("NON-STD" in l for l in labels) == 2 + 1   # big-five-nonstd + pseudo
        assert not any("STANDARD" in l or "NON-STD" in l
                       for l in labels if "INSTRUCTION" in l or "Source" in l)


@pytest.mark.asyncio
async def test_expand_collapse_roundtrip():
    app = _GridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        _cursor_to_pseudo(grid, table)
        await pilot.press("space")
        await pilot.pause()
        labels = _labels(table)
        for name in instructions_longtail():
            assert any(name in l for l in labels), f"{name} column missing after expand"
        assert any("… collapse" in l for l in labels)
        assert table.cursor_coordinate.column == _pseudo_column_index(grid)
        await pilot.press("space")
        await pilot.pause()
        labels = _labels(table)
        assert any("… +" in l for l in labels)
        assert not any("augment" in l for l in labels)
        assert table.cursor_coordinate.column == _pseudo_column_index(grid)


@pytest.mark.asyncio
async def test_longtail_toggle_roundtrip():
    app = _GridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        _cursor_to_pseudo(grid, table)
        await pilot.press("space")
        await pilot.pause()
        tail = instructions_longtail()[0]  # augment
        col = 2 + grid._active_harnesses().index(tail)
        table.cursor_coordinate = Coordinate(row=0, column=col)
        await pilot.press("space")
        await pilot.pause()
        assert grid.pending_entries() == {("global", tail, "AGENTS.md"): "link"}
        cell_text = str(table.get_cell_at(Coordinate(row=0, column=col)))
        assert "+" in cell_text, f"pending glyph missing: {cell_text!r}"


@pytest.mark.asyncio
async def test_collapse_with_pending_indicates():
    app = _GridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        _cursor_to_pseudo(grid, table)
        await pilot.press("space")
        await pilot.pause()
        tail = instructions_longtail()[0]
        col = 2 + grid._active_harnesses().index(tail)
        table.cursor_coordinate = Coordinate(row=0, column=col)
        await pilot.press("space")
        await pilot.pause()
        _cursor_to_pseudo(grid, table)
        await pilot.press("space")
        await pilot.pause()
        labels = _labels(table)
        assert any("±1" in l for l in labels), f"pending marker missing: {labels!r}"
        assert ("global", tail, "AGENTS.md") in grid.pending_entries()
        grid.clear_pending()
        await pilot.pause()
        assert not any("±" in l for l in _labels(table))


@pytest.mark.asyncio
async def test_collapse_state_is_per_kind():
    """Expanding the instruction grid's tail must not expand the skill grid's."""

    def _skill_row(slug: str = "alpha") -> SkillRow:
        agents = ("standard",) + skills_nonstandard_big_five() + skills_longtail()
        cells = {(a, "global"): SkillCell(linked=False, drift=False, skipped=False)
                 for a in agents}
        return SkillRow(slug=slug, source=f"x/{slug}", ref="main",
                        state="clean", cells=cells)

    class _BothApp(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_full_row()], id="ig")
            yield SkillGrid([_skill_row()], id="sg")

    app = _BothApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        igrid = app.query_one("#ig", InstructionGrid)
        itable = app.query_one("#instruction-table", DataTable)
        sgrid = app.query_one("#sg", SkillGrid)
        _cursor_to_pseudo(igrid, itable)
        await pilot.press("space")
        await pilot.pause()
        assert igrid._longtail_expanded is True
        assert sgrid._longtail_expanded is False


@pytest.mark.asyncio
async def test_press_i_on_standard_column_opens_registry_modal():
    """The inline coord.column==1 branch is replaced by the registry path:
    `i` on the standard column opens ColumnInfoModal with the exhaustive
    native list (kind-aware via context)."""
    from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal

    app = _GridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, ColumnInfoModal), \
            "ColumnInfoModal not pushed for the standard column"
        body = str(app.screen.query_one("#column-info-body").render())
        assert "instructions" in body and "(39)" in body
        assert "adal" in body  # a native reader, enumerated exhaustively


@pytest.mark.asyncio
async def test_press_i_on_pseudo_column_lists_collapsed_names():
    from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal

    app = _GridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        _cursor_to_pseudo(grid, table)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, ColumnInfoModal)
        body = str(app.screen.query_one("#column-info-body").render())
        for name in instructions_longtail():
            assert name in body
