from __future__ import annotations

from types import SimpleNamespace

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from agent_toolkit_tui.widgets._support import adjust_source_column_width


class _TableApp(App):
    def __init__(self, specs: list[tuple[str, int]]) -> None:
        super().__init__()
        self._specs = specs

    def compose(self) -> ComposeResult:
        yield DataTable(id="table")

    def on_mount(self) -> None:
        table = self.query_one("#table", DataTable)
        for label, width in self._specs:
            table.add_column(label, width=width)


@pytest.mark.asyncio
async def test_adjust_source_column_width_sizes_last_column_from_remaining_width():
    app = _TableApp([("Name", 20), ("State", 10), ("Source", 30)])
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#table", DataTable)
        event = SimpleNamespace(size=SimpleNamespace(width=100))

        adjust_source_column_width(table, event, fixed_width=42)

        source_col_key = list(table.columns.keys())[-1]
        assert table.columns[source_col_key].width == 58


@pytest.mark.asyncio
async def test_adjust_source_column_width_never_shrinks_source_below_minimum():
    app = _TableApp([("Name", 20), ("Source", 30)])
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#table", DataTable)
        event = SimpleNamespace(size=SimpleNamespace(width=30))

        adjust_source_column_width(table, event, fixed_width=42)

        source_col_key = list(table.columns.keys())[-1]
        assert table.columns[source_col_key].width == 10


def test_adjust_source_column_width_tolerates_empty_table():
    table = DataTable()
    event = SimpleNamespace(size=SimpleNamespace(width=100))

    adjust_source_column_width(table, event, fixed_width=42)

    assert list(table.columns.keys()) == []
