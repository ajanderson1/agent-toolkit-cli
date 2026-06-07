"""Pilot tests for view-pane (scroll offset) preservation across a toggle (#321).

Toggling a checkbox cell rebuilds the grid's DataTable (clear + re-add). Before
the fix, `_rebuild` saved only `cursor_coordinate`, not `scroll_y`, so
`DataTable.clear()` snapped the viewport back to the top — the pane jumped.

These tests build a grid with enough rows to overflow a tall-but-bounded
viewport, scroll down, place the cursor in the MIDDLE of the visible window,
record the settled offset, toggle the cell, and assert the viewport did not
move. The mid-pane cursor is what makes the test discriminate the fix: without
it, `clear()` drops scroll to 0 and the post-rebuild scroll-to-cursor lands the
cursor at a viewport edge — the pane visibly jumps; with it, the exact offset is
restored. (A cursor pinned at a viewport edge would mask the bug, since the
edge is where scroll-to-cursor lands anyway.)
"""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _row(slug: str, *, scope: str = "global") -> SkillRow:
    cells = {
        (a, scope): SkillCell(linked=False, drift=False, skipped=False)
        for a in INTERACTIVE_AGENTS
    }
    return SkillRow(slug=slug, source=f"x/{slug}", ref="main", state="clean", cells=cells)


class _ConstrainedApp(App):
    """Host app with a tall-but-bounded grid so the DataTable scrolls AND the
    cursor can sit mid-pane (not pinned to an edge). The mid-pane case is what
    discriminates the fix: without it, the post-rebuild scroll-to-cursor lands
    the cursor at a viewport edge and the pane visibly jumps; with it, the exact
    offset is restored."""

    CSS = "#g { height: 20; }"

    def __init__(self, rows: list[SkillRow]) -> None:
        super().__init__()
        self._rows = rows

    def compose(self) -> ComposeResult:
        yield SkillGrid(self._rows, id="g")


async def _scroll_with_cursor_mid_pane(pilot, table: DataTable) -> tuple[float, int]:
    """Focus the table, scroll down, place the cursor in the MIDDLE of the
    visible window, settle, and return (scroll_y, cursor_row)."""
    table.focus()
    await pilot.pause()
    table.scroll_to(y=20, animate=False, force=True)
    await pilot.pause()
    mid_row = int(table.scroll_y) + table.size.height // 2
    table.cursor_coordinate = Coordinate(row=mid_row, column=1)
    await pilot.pause()
    # Precondition: genuinely scrolled (otherwise the assertion is vacuous).
    assert table.scroll_y > 0, f"expected a scrolled viewport, got scroll_y={table.scroll_y}"
    return table.scroll_y, table.cursor_coordinate.row


@pytest.mark.asyncio
async def test_toggle_preserves_scroll_offset():
    """Toggling a cell (space) deep in the list must not move the viewport."""
    rows = [_row(f"skill-{i:02d}") for i in range(60)]
    app = _ConstrainedApp(rows)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = app.query_one("#skill-table", DataTable)
        scroll_before, row_before = await _scroll_with_cursor_mid_pane(pilot, table)

        await pilot.press("space")
        await pilot.pause()

        assert table.scroll_y == scroll_before, (
            f"viewport jumped: scroll_y {scroll_before} -> {table.scroll_y}"
        )
        assert table.cursor_coordinate.row == row_before, (
            f"cursor row moved: {row_before} -> {table.cursor_coordinate.row}"
        )
        assert app.query_one("#g", SkillGrid).pending_entries() != {}, "toggle should register"


@pytest.mark.asyncio
async def test_toggle_column_preserves_scroll_offset():
    """`a` (toggle whole column) must also leave the viewport put."""
    rows = [_row(f"skill-{i:02d}") for i in range(60)]
    app = _ConstrainedApp(rows)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = app.query_one("#skill-table", DataTable)
        scroll_before, _ = await _scroll_with_cursor_mid_pane(pilot, table)

        await pilot.press("a")
        await pilot.pause()

        assert table.scroll_y == scroll_before, (
            f"viewport jumped on column toggle: {scroll_before} -> {table.scroll_y}"
        )


# ---------------------------------------------------------------------------
# The fix is shared across all four grids; assert it lands in agent + instruction
# grids too (pi_grid shares the identical _rebuild edit but has no per-scope
# toggle keys to drive headlessly — its preservation is covered by the shared
# code path + the agent/instruction proofs).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_grid_toggle_preserves_scroll_offset():
    """AgentGrid: mid-pane toggle must not move the viewport (#321)."""
    from agent_toolkit_tui.agent_state import INTERACTIVE_HARNESSES, AgentCell, AgentRow
    from agent_toolkit_tui.widgets.agent_grid import AgentGrid

    def _arow(slug: str) -> AgentRow:
        return AgentRow(
            slug=slug, source=f"x/{slug}", ref="main",
            cells={(h, "global"): AgentCell(linked=False) for h in INTERACTIVE_HARNESSES},
        )

    class _A(App):
        CSS = "#g { height: 20; }"

        def compose(self) -> ComposeResult:
            grid = AgentGrid([_arow(f"agent-{i:02d}") for i in range(60)], id="g")
            grid.set_scope("global")
            yield grid

    app = _A()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = app.query_one("#agent-table", DataTable)
        scroll_before, _ = await _scroll_with_cursor_mid_pane(pilot, table)
        await pilot.press("space")
        await pilot.pause()
        assert table.scroll_y == scroll_before, (
            f"agent grid viewport jumped: {scroll_before} -> {table.scroll_y}"
        )


@pytest.mark.asyncio
async def test_instruction_grid_toggle_preserves_scroll_offset():
    """InstructionGrid: mid-pane toggle must not move the viewport (#321).

    Instruction locks are single-slug today, so to exercise scrolling we mount a
    grid with many synthetic rows directly.
    """
    from agent_toolkit_tui.instruction_state import (
        INTERACTIVE_HARNESSES, InstructionCell, InstructionRow,
    )
    from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid

    def _irow(slug: str) -> InstructionRow:
        return InstructionRow(
            slug=slug, source="AGENTS.md", canonical_exists=True,
            cells={(h, "global"): InstructionCell(linked=False, conflict=False)
                   for h in INTERACTIVE_HARNESSES},
        )

    class _A(App):
        CSS = "#g { height: 20; }"

        def compose(self) -> ComposeResult:
            grid = InstructionGrid([_irow(f"AGENTS-{i:02d}.md") for i in range(60)], id="g")
            grid.set_scope("global")
            yield grid

    app = _A()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = app.query_one("#instruction-table", DataTable)
        scroll_before, _ = await _scroll_with_cursor_mid_pane(pilot, table)
        # Column 2 is the first interactive harness (0=slug, 1=general).
        from textual.coordinate import Coordinate

        table.cursor_coordinate = Coordinate(row=table.cursor_coordinate.row, column=2)
        await pilot.pause()
        scroll_before = table.scroll_y
        await pilot.press("space")
        await pilot.pause()
        assert table.scroll_y == scroll_before, (
            f"instruction grid viewport jumped: {scroll_before} -> {table.scroll_y}"
        )


# ---------------------------------------------------------------------------
# Robustness of the saved-scroll restore on non-toggle rebuilds (boundary cases
# the toggle tests don't reach). These document behavior the self-review flagged:
# on a content-shrinking rebuild the restore is clamped (no over-scroll), and an
# empty rebuild is a safe no-op.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shrinking_rebuild_clamps_scroll_within_range():
    """A rebuild that shortens the list must leave scroll within [0, max] — the
    restored offset can't over-scroll past the new (shorter) content."""
    rows = [_row(f"skill-{i:02d}") for i in range(60)]
    app = _ConstrainedApp(rows)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = app.query_one("#skill-table", DataTable)
        await _scroll_with_cursor_mid_pane(pilot, table)  # scrolled near y=20

        # Shrink the row set far below the saved offset, then rebuild.
        grid = app.query_one("#g", SkillGrid)
        grid.set_rows([_row("only-0"), _row("only-1")])
        await pilot.pause()

        assert 0 <= table.scroll_y <= table.max_scroll_y, (
            f"scroll out of range after shrink: scroll_y={table.scroll_y}, "
            f"max={table.max_scroll_y}"
        )


@pytest.mark.asyncio
async def test_empty_rebuild_is_safe_noop():
    """Rebuilding to an empty grid must not raise and leaves scroll at 0."""
    rows = [_row(f"skill-{i:02d}") for i in range(60)]
    app = _ConstrainedApp(rows)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        table = app.query_one("#skill-table", DataTable)
        grid = app.query_one("#g", SkillGrid)
        grid.set_rows([])  # _rebuild over an empty set — scroll_to(0,0) no-op
        await pilot.pause()
        assert table.scroll_y == 0
        assert grid.row_count == 0
