"""Shared helpers for TUI widgets."""
from __future__ import annotations

from rich.text import Text
from rich.cells import cell_len
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

    # Textual calculates ``content_width`` on the next refresh. Measure the
    # current cells directly so rebuilds fit new source values immediately.
    header_width = cell_len(str(table.columns[source_col_key].label))
    content_width = max(
        (cell_len(str(value)) for value in table.get_column(source_col_key)),
        default=header_width,
    )
    fixed_render_width = sum(
        column.get_render_width(table)
        for key, column in table.columns.items()
        if key != source_col_key
    )
    fixed_column_count = len(table.columns) - 1
    configured_render_width = fixed_width + (
        2 * table.cell_padding * fixed_column_count
    )
    fixed_render_width = max(fixed_render_width, configured_render_width)
    source_padding = 2 * table.cell_padding
    available = max(10, viewport_width - fixed_render_width - source_padding)
    width = min(available, max(10, content_width))

    table.columns[source_col_key].width = width
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
