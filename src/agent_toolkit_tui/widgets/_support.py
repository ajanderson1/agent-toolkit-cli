"""Shared helpers for TUI widgets."""
from __future__ import annotations

from rich.text import Text
from textual.events import Resize
from textual.widgets import DataTable


def sync_table(
    table: DataTable,
    columns: list[tuple[str, int]],
    rows: list[tuple[str, list[str | Text]]],
) -> None:
    """Update changed cells in place; rebuild only when the structure changes.

    All values are freshly computed by the grid, not cached inventory state.
    Fixed-width columns let cell updates avoid a full-table dimension scan.
    """
    same_columns = len(columns) == len(table.columns) and all(
        column.label == Text.from_markup(label) and column.width == width
        for column, (label, width) in zip(table.ordered_columns, columns)
    )
    same_rows = [key.value for key in table.rows] == [key for key, _ in rows]
    if same_columns and same_rows:
        column_keys = list(table.columns)
        for key, values in rows:
            for column_key, old, new in zip(column_keys, table.get_row(key), values):
                if old != new:
                    table.update_cell(key, column_key, new)
        return

    table.clear(columns=True)
    for label, width in columns:
        table.add_column(label, width=width)
    for key, values in rows:
        table.add_row(*values, key=key)


def set_source_column_width(
    table: DataTable,
    viewport_width: int,
    fixed_width: int,
) -> None:
    """Set the Source column to remaining viewport width."""
    if not table.columns:
        return

    # Last column is always Source in TUI grids.
    source_col_key = list(table.columns.keys())[-1]

    # Textual DataTable has padding and border.
    available = max(10, viewport_width - fixed_width)

    table.columns[source_col_key].width = available
    table.refresh()


def current_source_column_width(table: DataTable, default: int = 30) -> int:
    """Return the current Source column width before a table rebuild."""
    if not table.columns:
        return default
    source_col_key = list(table.columns.keys())[-1]
    return table.columns[source_col_key].width or default


def adjust_source_column_width(
    table: DataTable,
    event: Resize,
    fixed_width: int,
) -> None:
    """Adjust the Source column to take up the remaining width."""
    set_source_column_width(table, event.size.width, fixed_width)
