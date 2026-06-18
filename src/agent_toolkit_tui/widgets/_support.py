from textual.widgets import DataTable
from textual.events import Resize

def adjust_source_column_width(table: DataTable, event: Resize, fixed_width: int) -> None:
    """Adjust the Source column to take up the remaining width."""
    if not table.columns:
        return

    source_col_key = list(table.columns.keys())[-1]

    # Textual DataTable has padding and border.
    # 2 chars per column for padding.
    # Terminal width minus the known fixed columns minus the padding.
    # Each column has roughly 2 spaces of padding.
    total_padding = len(table.columns) * 2 + 2
    available = max(10, event.size.width - fixed_width - total_padding)
    table.columns[source_col_key].width = available
    table.refresh()
