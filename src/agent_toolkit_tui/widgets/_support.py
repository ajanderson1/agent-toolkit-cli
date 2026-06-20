"""Shared helpers for TUI widgets."""
from __future__ import annotations

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
