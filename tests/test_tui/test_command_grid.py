from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from agent_toolkit_tui.command_state import CommandCell, CommandRow
from agent_toolkit_tui.widgets.command_grid import CommandGrid
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal


class CommandGridApp(App):
    def compose(self) -> ComposeResult:
        yield CommandGrid(
            [
                CommandRow(
                    slug="demo",
                    source="owner/repo",
                    ref="main",
                    cells={("standard", "global"): CommandCell(False)},
                )
            ]
        )


def test_command_grid_renders_rows():
    grid = CommandGrid(
        [
            CommandRow(
                slug="demo",
                source="owner/repo",
                ref="main",
                cells={("standard", "global"): CommandCell(False)},
            )
        ]
    )
    assert grid.row_count == 1
    assert grid.row_slugs == ["demo"]


@pytest.mark.asyncio
async def test_command_headers_use_standard_first():
    app = CommandGridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one(CommandGrid)
        table = app.query_one("#command-table", DataTable)
        headers = [str(column.label) for column in table.columns.values()]
        assert headers[1].startswith("Standard (2)"), headers
        assert any(header.startswith("Pi") for header in headers), headers
        assert any(header.startswith("Gemini") for header in headers), headers
        assert not any(header.startswith("Claude") for header in headers), headers
        assert not any(header.startswith("claude-code") for header in headers), headers

        grid.set_scope("project")
        await pilot.pause()
        headers = [str(column.label) for column in table.columns.values()]
        assert headers[1].startswith("Standard (3)"), headers


@pytest.mark.asyncio
async def test_standard_header_click_opens_info():
    from rich.text import Text
    from agent_toolkit_tui.column_info import get_column_info

    app = CommandGridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one(CommandGrid)
        grid.set_scope("project")
        await pilot.pause()
        table = app.query_one("#command-table", DataTable)
        grid.post_message(
            DataTable.HeaderSelected(
                table,
                column_key=list(table.columns)[1],
                column_index=1,
                label=Text(str(list(table.columns.values())[1].label)),
            )
        )
        await pilot.pause()
        assert isinstance(app.screen, ColumnInfoModal)
        expected = get_column_info(
            "standard", asset_type="command", context={"scope": "project"},
        )
        assert app.screen._info.title == expected.title
        body = "\n".join(expected.lines)
        assert "Devin" in body


@pytest.mark.asyncio
async def test_space_on_standard_queues_pending():
    app = CommandGridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one(CommandGrid)
        table = app.query_one("#command-table", DataTable)
        # Move cursor to standard cell (col 1)
        table.cursor_coordinate = table.cursor_coordinate._replace(column=1) if hasattr(table.cursor_coordinate, '_replace') else type(table.cursor_coordinate)(0, 1)
        from textual.coordinate import Coordinate
        table.cursor_coordinate = Coordinate(0, 1)
        grid.action_toggle_cell()
        await pilot.pause()
        assert ("global", "standard", "demo") in grid.pending_entries()
