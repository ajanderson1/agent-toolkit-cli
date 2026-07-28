from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from agent_toolkit_tui.command_state import CommandCell, CommandRow
from agent_toolkit_tui.widgets.command_grid import CommandGrid


class CommandGridApp(App):
    def compose(self) -> ComposeResult:
        yield CommandGrid(
            [
                CommandRow(
                    slug="demo",
                    source="owner/repo",
                    ref="main",
                    cells={},
                )
            ]
        )


def test_command_grid_renders_rows():
    grid = CommandGrid([CommandRow(slug="demo", source="owner/repo", ref="main", cells={("claude-code", "global"): CommandCell(False)})])
    assert grid.row_count == 1
    assert grid.row_slugs == ["demo"]


@pytest.mark.asyncio
async def test_command_headers_use_display_labels():
    """#448 sweep escapee: headers rendered raw catalog keys (#478 R6)."""
    app = CommandGridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#command-table", DataTable)
        headers = [str(column.label) for column in table.columns.values()]
        assert any(header.startswith("Claude") for header in headers), headers
        assert any(header.startswith("Gemini") for header in headers), headers
        assert not any(header.startswith("claude-code") for header in headers), headers
        assert not any(header.startswith("gemini-cli") for header in headers), headers
