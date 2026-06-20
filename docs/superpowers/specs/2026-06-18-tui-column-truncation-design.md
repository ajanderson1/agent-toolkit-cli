# TUI Column Truncation Design

## Problem
DataTable scrolls horizontally. User wants columns to stretch to terminal width, but truncate with `...` if too narrow. No horizontal scroll. "Source" column contains long paths and causes overflow.

## Approach
Dynamic column width via `on_resize`.

## Details
1. Disable DataTable horizontal scroll: `show_horizontal_scrollbar=False` or allow it but we prevent overflow.
2. In `_rebuild` or `on_resize` of grid widgets (`agent_grid.py`, `command_grid.py`, etc.), calculate total width of fixed columns (Name, State, Harnesses).
3. Assign remaining width to the "Source" column using `DataTable.columns[col_key].width = remainder`.
4. Render cell content in "Source" using `rich.text.Text(path, no_wrap=True, overflow="ellipsis")`.
5. Trigger a table refresh on resize if needed.
