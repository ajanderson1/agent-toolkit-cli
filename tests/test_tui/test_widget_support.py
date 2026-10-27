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
async def test_adjust_source_column_width_sizes_last_column_to_content_when_room_permits():
    app = _TableApp([("Name", 20), ("State", 10), ("Source", 30)])
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#table", DataTable)
        table.add_row("demo", "clean", "owner/repository-with-a-long-source-name")
        await pilot.pause()
        event = SimpleNamespace(size=SimpleNamespace(width=100))

        adjust_source_column_width(table, event, fixed_width=42)

        source_col_key = list(table.columns.keys())[-1]
        assert table.columns[source_col_key].width == len("owner/repository-with-a-long-source-name")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("grid_shape", "fixed_widths"),
    [
        ("skill", (20, 14, 14, 14, 14, 10)),
        ("command", (22, 14, 14, 14, 10)),
        ("agent", (22, 14, 14, 14, 14, 10)),
        ("instruction", (22, 16)),
        ("pi-extension", (24, 14, 12)),
        ("mcp", (22, 16, 16, 16, 16, 10)),
    ],
)
async def test_adjust_source_column_width_accounts_for_padding_in_each_grid_shape(
    grid_shape: str, fixed_widths: tuple[int, ...]
):
    specs = [
        (f"Column {index}", width) for index, width in enumerate(fixed_widths)
    ]
    app = _TableApp([*specs, ("Source", 30)])
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#table", DataTable)
        table.add_row(*(["value"] * len(fixed_widths)), "source-value-that-needs-capping")
        await pilot.pause()
        source_col_key = list(table.columns.keys())[-1]
        fixed_render_width = sum(
            column.get_render_width(table)
            for key, column in table.columns.items()
            if key != source_col_key
        )
        viewport_width = fixed_render_width + (2 * table.cell_padding) + 15

        adjust_source_column_width(
            table,
            SimpleNamespace(size=SimpleNamespace(width=viewport_width)),
            fixed_width=sum(fixed_widths),
        )

        assert table.columns[source_col_key].width == 15, grid_shape
        assert sum(column.get_render_width(table) for column in table.columns.values()) <= viewport_width, grid_shape


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
