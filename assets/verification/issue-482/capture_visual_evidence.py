#!/usr/bin/env python3
"""R1 visual capture for #482 — Commands Standard column."""
from __future__ import annotations

import asyncio
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.command_state import CommandCell, CommandRow
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal
from agent_toolkit_tui.widgets.command_grid import CommandGrid

OUT = Path(__file__).resolve().parent


class CaptureApp(App):
    def __init__(self, scope: str) -> None:
        super().__init__()
        self._scope = scope

    def compose(self) -> ComposeResult:
        cells = {
            ("standard", self._scope): CommandCell(False),
            ("pi", self._scope): CommandCell(False),
            ("gemini-cli", self._scope): CommandCell(False),
        }
        grid = CommandGrid(
            [CommandRow(slug="demo", source="o/r", ref="main", cells=cells)],
            id="command-grid",
        )
        grid.set_scope(self._scope)  # type: ignore[arg-type]
        yield grid


async def capture(scope: str) -> dict:
    app = CaptureApp(scope)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        grid = app.query_one("#command-grid", CommandGrid)
        table = app.query_one("#command-table", DataTable)
        headers = [str(c.label) for c in table.columns.values()]
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
        info = get_column_info("standard", asset_type="command", context={"scope": scope})
        svg = app.export_screenshot(title=f"command-standard-{scope}")
        (OUT / f"command-standard-{scope}.svg").write_text(svg)
        await pilot.press("escape")
        await pilot.pause()
        table.cursor_coordinate = Coordinate(0, 1)
        grid.action_toggle_cell()
        await pilot.pause()
        pending = grid.pending_entries()
        svg2 = app.export_screenshot(title=f"command-standard-{scope}-pending")
        (OUT / f"command-standard-{scope}-pending.svg").write_text(svg2)
        return {
            "scope": scope,
            "headers": headers,
            "info_title": info.title,
            "info_lines": info.lines,
            "pending": {str(k): v for k, v in pending.items()},
        }


async def main() -> None:
    results = [await capture(scope) for scope in ("global", "project")]
    lines: list[str] = []
    for r in results:
        lines.append(f"## scope={r['scope']}")
        lines.append(f"headers: {r['headers']}")
        lines.append(f"info: {r['info_title']}")
        lines.extend(f"  {line}" for line in r["info_lines"])
        lines.append(f"pending: {r['pending']}")
        lines.append("")
    text = "\n".join(lines) + "\n"
    (OUT / "visual-capture.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    asyncio.run(main())
