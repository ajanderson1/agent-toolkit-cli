"""Shared helpers for TUI widgets."""
from __future__ import annotations

from rich.cells import cell_len
from textual.events import Resize
from textual.widgets import DataTable


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
