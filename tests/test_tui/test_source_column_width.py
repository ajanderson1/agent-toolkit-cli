from __future__ import annotations

from types import SimpleNamespace

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from agent_toolkit_tui.command_state import interactive_harnesses, CommandCell, CommandRow
from agent_toolkit_tui.widgets.command_grid import CommandGrid


@pytest.mark.asyncio
async def test_command_grid_sizes_source_column_to_text_when_room_permits():
    row = CommandRow(
        slug="demo",
        source="owner/repo-with-a-long-source-name",
        ref="main",
        cells={(interactive_harnesses("global")[0], "global"): CommandCell(False)},
    )

    class _A(App):
        def compose(self) -> ComposeResult:
            yield CommandGrid([row], id="g")

    app = _A()
    async with app.run_test(size=(220, 40)) as pilot:
        await pilot.pause()
        grid = app.query_one("#g", CommandGrid)
        table = app.query_one("#command-table", DataTable)

        source_col = list(table.columns.values())[-1]
        assert source_col.width == len(row.source)

        grid.on_resize(SimpleNamespace(size=SimpleNamespace(width=80)))
        assert source_col.width == 10
