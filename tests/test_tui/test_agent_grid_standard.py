"""Standard column on the agents tab (#361).

The standard slot leads the harness columns; claude-code and cursor are
absorbed into it (both read .claude/agents natively at both scopes).
Pressing `i` on the Standard column opens the registry-backed
ColumnInfoModal listing the covered harnesses per scope.
"""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.agent_state import INTERACTIVE_HARNESSES, AgentCell, AgentRow
from agent_toolkit_tui.widgets.agent_grid import AgentGrid


def _row(slug: str = "demo", scope: str = "global") -> AgentRow:
    cells = {(h, scope): AgentCell(linked=False) for h in INTERACTIVE_HARNESSES}
    return AgentRow(slug=slug, source=f"x/{slug}", ref="main", cells=cells)


class _A(App):
    def compose(self) -> ComposeResult:
        yield AgentGrid([_row()], id="g")


@pytest.mark.asyncio
async def test_columns_standard_first_then_noncovered_main():
    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#agent-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        from agent_toolkit_cli.agent_adapters.standard import agents_standard_covered

        assert labels[0] == "Agent ⓘ"
        assert labels[1] == f"Standard ({len(agents_standard_covered('global'))}) ⓘ"
        assert not any("Claude Code" in lbl for lbl in labels)  # absorbed
        assert not any("claude-code" in lbl for lbl in labels)
        # cursor is covered at both scopes → NO Cursor column either.
        assert not any("Cursor" in lbl for lbl in labels)
        assert any("OpenCode" in lbl for lbl in labels)
        assert any("Pi" in lbl for lbl in labels)
        assert not any("… +" in lbl or "\n" in lbl for lbl in labels)


@pytest.mark.asyncio
async def test_press_i_on_standard_column_opens_registry_modal():
    from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#agent-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, ColumnInfoModal)
        body = str(app.screen.query_one("#column-info-body").render())
        assert "agents" in body
        # Covered set (global): claude-code, kode, neovate, cortex, cursor.
        assert "Kode" in body and "Neovate" in body and "Cortex" in body
        assert "Cursor" in body
        # The global-scope panel (the grid default) carries the devin
        # project-only NOTE (devin is NOT in the global covered list).
        assert "Devin" in body
        assert "project scope only" in body


@pytest.mark.asyncio
async def test_standard_modal_at_project_scope_lists_devin_without_note():
    """Scope flip: at project scope devin is simply covered — it appears in
    the plain covered list and the project-only NOTE line is absent."""
    from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal

    class _P(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid([_row(scope="project")], id="g")

    app = _P()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", AgentGrid)
        grid.set_scope("project")
        await pilot.pause()
        table = app.query_one("#agent-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, ColumnInfoModal)
        body = str(app.screen.query_one("#column-info-body").render())
        # devin is in the covered list as a plain bullet...
        assert "Devin" in body
        # ...and the global-panel NOTE is gone.
        assert "project scope only" not in body


@pytest.mark.asyncio
async def test_press_i_on_nonstandard_column_falls_through_to_cell_info():
    """Registry dispatch must not swallow the existing per-cell path: `i` on
    a NON-standard harness column (Pi) opens CellInfoScreen, not the modal."""
    from agent_toolkit_tui.screens.cell_info import CellInfoScreen
    from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#agent-table", DataTable)
        pi_col = 1 + INTERACTIVE_HARNESSES.index("pi")
        table.cursor_coordinate = Coordinate(row=0, column=pi_col)
        table.focus()
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, CellInfoScreen)
        assert not isinstance(app.screen, ColumnInfoModal)


@pytest.mark.asyncio
async def test_standard_cell_toggles_like_any_other():
    """Space on the standard cell queues link — the slot is interactive."""
    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", AgentGrid)
        g.set_scope("global")
        table = app.query_one("#agent-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries().get(("global", "standard", "demo")) == "link"
