from __future__ import annotations

from types import SimpleNamespace

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from agent_toolkit_tui.command_state import INTERACTIVE_HARNESSES, CommandCell, CommandRow
from agent_toolkit_tui.widgets.command_grid import CommandGrid


def _resize(width: int) -> SimpleNamespace:
    return SimpleNamespace(size=SimpleNamespace(width=width))


@pytest.mark.asyncio
async def test_command_grid_resize_adjusts_source_column_width():
    row = CommandRow(
        slug="demo",
        source="owner/repo-with-a-long-source-name",
        ref="main",
        cells={(INTERACTIVE_HARNESSES[0], "global"): CommandCell(False)},
    )

    class _A(App):
        def compose(self) -> ComposeResult:
            yield CommandGrid([row], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", CommandGrid)
        table = app.query_one("#command-table", DataTable)

        grid.on_resize(_resize(220))

        source_col = list(table.columns.values())[-1]
        fixed_width = 22 + (14 * len(INTERACTIVE_HARNESSES)) + 10
        assert source_col.width == 220 - fixed_width
