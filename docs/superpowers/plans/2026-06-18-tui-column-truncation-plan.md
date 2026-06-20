# TUI Column Truncation Plan

## 1. Grid Widget Updates
Modify the following to hook `on_resize` and calculate available width for the `Source` column:
- `src/agent_toolkit_tui/widgets/agent_grid.py`
- `src/agent_toolkit_tui/widgets/command_grid.py`
- `src/agent_toolkit_tui/widgets/instruction_grid.py`
- `src/agent_toolkit_tui/widgets/mcp_grid.py`
- `src/agent_toolkit_tui/widgets/pi_grid.py`
- `src/agent_toolkit_tui/widgets/skill_grid.py`

## 2. Shared Base or Mixin
Extract the width calculation to a helper method in a shared module (e.g., `_support.py` or `composition.py`) to avoid duplication.
Pass the `DataTable` and the window width, let it adjust the `Source` column width.

## 3. Cell Truncation
Ensure the source cells are wrapped in `rich.text.Text(val, no_wrap=True, overflow="ellipsis")`.
