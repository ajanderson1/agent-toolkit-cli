"""Standard / Non-standard column groups on the skill grid (#351).

Spike test first: pins the two-line `header_height=2` DataTable header
mechanism the whole feature depends on (verified on Textual 8.2.5 at review
time). Behavior tests drive the real SkillGrid through the same app harness
as tests/test_tui/test_skill_grid_column_info.py.
"""
from __future__ import annotations

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_tui.composition import skills_longtail, skills_nonstandard_big_five
from agent_toolkit_tui.skill_state import SkillCell, SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


@pytest.mark.asyncio
async def test_datatable_two_line_header_renders():
    class Probe(App):
        def compose(self) -> ComposeResult:
            yield DataTable(id="t")

        def on_mount(self) -> None:
            t = self.query_one("#t", DataTable)
            t.header_height = 2
            label = Text()
            label.append("NON-STD\n", style="dim")
            label.append("claude-code ⓘ")
            t.add_column(label, width=14)
            t.add_row("x")

    app = Probe()
    async with app.run_test() as pilot:
        t = app.query_one("#t", DataTable)
        assert t.header_height == 2
        # Both lines present in the rendered header region.
        # Use Strip.text, not str(strip) — the repr only incidentally embeds
        # segment text and is not a stable API.
        text = "\n".join(strip.text for strip in [t.render_line(0), t.render_line(1)])
        assert "NON-STD" in text and "claude-code" in text


# ---------------------------------------------------------------------------
# Behavior tests — real SkillGrid through the app harness
# ---------------------------------------------------------------------------

def _full_cells(scope: str = "global") -> dict:
    """Cells over the FULL composition: _toggle_at bails on cell=None, so
    tail-toggle tests need tail cells too (#351 fixture note)."""
    agents = ("standard",) + skills_nonstandard_big_five() + skills_longtail()
    return {(a, scope): SkillCell(linked=False, drift=False, skipped=False)
            for a in agents}


def _row(slug: str, *, scope: str = "global") -> SkillRow:
    return SkillRow(
        slug=slug, source=f"x/{slug}", ref="main",
        state="clean", cells=_full_cells(scope),
    )


class _GridApp(App):
    def __init__(self, rows: list[SkillRow]) -> None:
        super().__init__()
        self._fixture_rows = rows

    def compose(self) -> ComposeResult:
        yield SkillGrid(self._fixture_rows, id="g")


def _labels(table: DataTable) -> list[str]:
    return [str(c.label) for c in table.columns.values()]


def _pseudo_column_index(grid: SkillGrid) -> int:
    return 1 + len(grid._active_agents())


def _cursor_to_pseudo(grid: SkillGrid, table: DataTable, *, row: int = 0) -> None:
    """Park the cursor on the pseudo-column with the table focused — the
    grid's `space` binding resolves from the focused widget's ancestor chain,
    so it never fires while the filter Input holds focus (the #249 default)."""
    table.cursor_coordinate = Coordinate(row=row, column=_pseudo_column_index(grid))
    table.focus()


def _tail_display(i: int) -> str:
    return AGENTS[skills_longtail()[i]].display_name


@pytest.mark.asyncio
async def test_default_columns_collapsed():
    app = _GridApp([_row("alpha")])
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#skill-table", DataTable)
        labels = _labels(table)
        # slug + standard + claude-code + pi + pseudo + state + source
        assert any("standard" in l for l in labels)
        assert any("… +" in l for l in labels)
        assert not any("codex" in l for l in labels)          # standard → no own column
        assert not any(_tail_display(0) in l for l in labels)  # tail collapsed
        assert sum("STANDARD" in l for l in labels) == 1
        assert sum("NON-STD" in l for l in labels) == 2 + 1   # big-five-nonstd + pseudo
        assert not any("STANDARD" in l or "NON-STD" in l
                       for l in labels if "State" in l or "Source" in l)


@pytest.mark.asyncio
async def test_expand_collapse_in_place_preserves_scroll():
    # Enough rows to overflow the default test viewport vertically (#321 lesson).
    rows = [_row(f"skill-{i:02d}") for i in range(40)]
    app = _GridApp(rows)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", SkillGrid)
        table = app.query_one("#skill-table", DataTable)
        assert table.max_scroll_y > 0, "fixture must overflow the container"
        # Park the viewport mid-list with the cursor inside it, on the pseudo-column.
        _cursor_to_pseudo(grid, table, row=8)
        table.scroll_to(y=5, animate=False, force=True)
        await pilot.pause()
        saved_y = table.scroll_y
        assert saved_y > 0

        await pilot.press("space")
        await pilot.pause()
        labels = _labels(table)
        for i in range(3):
            assert any(_tail_display(i) in l for l in labels), \
                f"{_tail_display(i)} column missing after expand"
        assert any("… collapse" in l for l in labels)
        assert not any("… +" in l for l in labels)
        # Cursor follows the pseudo-column to its NEW index.
        assert table.cursor_coordinate.column == _pseudo_column_index(grid)
        assert table.scroll_y == saved_y

        await pilot.press("space")
        await pilot.pause()
        labels = _labels(table)
        assert any("… +" in l for l in labels)
        assert not any(_tail_display(0) in l for l in labels)
        assert table.cursor_coordinate.column == _pseudo_column_index(grid)
        assert table.scroll_y == saved_y


@pytest.mark.asyncio
async def test_longtail_toggle_roundtrip():
    app = _GridApp([_row("alpha")])
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", SkillGrid)
        table = app.query_one("#skill-table", DataTable)
        # Expand.
        _cursor_to_pseudo(grid, table)
        await pilot.press("space")
        await pilot.pause()
        # Move to the first long-tail agent column and toggle it.
        tail_agent = skills_longtail()[0]
        grid.cursor_to_cell(row_slug="alpha", agent_name=tail_agent)
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert grid.pending_entries() == {("global", tail_agent, "alpha"): "link"}
        col = grid._column_index(tail_agent)
        cell_text = str(table.get_cell_at(Coordinate(row=0, column=col)))
        assert "+" in cell_text, f"pending glyph missing: {cell_text!r}"


@pytest.mark.asyncio
async def test_collapse_with_pending_indicates_and_applies():
    app = _GridApp([_row("alpha")])
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", SkillGrid)
        table = app.query_one("#skill-table", DataTable)
        tail_agent = skills_longtail()[0]
        # Expand → queue a toggle on a tail agent → collapse.
        _cursor_to_pseudo(grid, table)
        await pilot.press("space")
        await pilot.pause()
        grid.cursor_to_cell(row_slug="alpha", agent_name=tail_agent)
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        _cursor_to_pseudo(grid, table)
        await pilot.press("space")
        await pilot.pause()
        # Keep-and-indicate: marker on the pseudo label, op still pending.
        labels = _labels(table)
        assert any("±1" in l for l in labels), f"pending marker missing: {labels!r}"
        assert ("global", tail_agent, "alpha") in grid.pending_entries()
        # Revert clears the ops AND the marker.
        grid.clear_pending()
        await pilot.pause()
        assert grid.pending_entries() == {}
        labels = _labels(table)
        assert not any("±" in l for l in labels), f"marker survived revert: {labels!r}"


@pytest.mark.asyncio
async def test_filter_does_not_reset_expansion():
    app = _GridApp([_row("alpha"), _row("beta")])
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", SkillGrid)
        table = app.query_one("#skill-table", DataTable)
        _cursor_to_pseudo(grid, table)
        await pilot.press("space")
        await pilot.pause()
        grid.set_filter("alpha")
        await pilot.pause()
        labels = _labels(table)
        assert any(_tail_display(0) in l for l in labels), \
            "filter must affect rows only, not the expanded columns"
        # Rows actually filtered.
        assert table.row_count == 1


@pytest.mark.asyncio
async def test_scope_toggle_does_not_reset_expansion():
    """AC4: only the pseudo-column collapses the long tail — scope toggle
    clears pending but keeps the expanded state."""
    app = _GridApp([_row("alpha")])
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", SkillGrid)
        table = app.query_one("#skill-table", DataTable)
        _cursor_to_pseudo(grid, table)
        await pilot.press("space")
        await pilot.pause()
        assert grid._longtail_expanded is True
        grid.set_scope("project")
        await pilot.pause()
        assert grid._longtail_expanded is True
