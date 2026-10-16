# Spec: Clean Asset Types Sidebar Navigation

**Issue:** #526
**Date:** 2026-10-16
**Status:** Firm

## 1. Intent & Context
The `agent-toolkit-tui` terminal cockpit provides a left rail (`Vertical#asset-types-sidebar`) housing an `OptionList` (`SidebarOptionList#asset-types-list`) to navigate between managed asset types.

Currently, the options in `#asset-types-list` contain:
- Numeric prefixes formatted with dim brackets: `[dim]1 -[/dim] Instructions`, `[dim]2 -[/dim] Commands`, `[dim]3 -[/dim] Skills`, `[dim]4 -[/dim] Agents`, `[dim]5 -[/dim] MCPs`, `[dim]6 -[/dim] Pi Extensions`.
- Visual divider lines separating groups of asset types:
  - `Option("─────────────", id="asset-type-separator-1", disabled=True)` between Instructions and Commands
  - `Option("─────────────", id="asset-type-separator-2", disabled=True)` between MCPs and Pi Extensions

These lines and numbers add unnecessary visual clutter to the left-hand navigation rail. The objective is to remove the divider lines and numeric prefixes, leaving a clean list displaying only the plain asset type names (e.g. "Instructions", "Commands", "Skills", "Agents", "MCPs", "Pi Extensions").

## 2. Goals & Non-Goals

### Goals
- Render each sidebar option with only the clean plural asset type label produced by `_asset_type_label(asset_type, plural=True)` (e.g., "Instructions", "Commands", "Skills", "Agents", "MCPs", "Pi Extensions").
- Remove all separator options (`asset-type-separator-1`, `asset-type-separator-2`) from `#asset-types-list`.
- Preserve existing option IDs (`asset-type-instruction`, `asset-type-command`, `asset-type-skill`, `asset-type-agent`, `asset-type-mcp`, `asset-type-pi-extension`) so that highlight synchronization (`get_option_index(f"asset-type-{asset_type}")`) and event selection handlers remain robust and uninterrupted.
- Preserve keyboard navigation bindings `1`–`6` on `SidebarOptionList` for muscle memory navigation when the sidebar is focused.
- Maintain safe handling in `on_option_list_option_selected`.
- Update existing test assertions in `tests/test_tui/test_instruction_grid.py` and other test files that expect separators or verify prompt contents.

### Non-Goals
- Changing the ordering of asset types in the sidebar.
- Changing grid contents, table headers, or scope toggling.
- Removing keyboard shortcuts `1`–`6` when the sidebar is focused.

## 3. Technical Design

### 3.1 Sidebar Option Construction in `src/agent_toolkit_tui/app.py`
In `TUIApp.compose()`, update the `SidebarOptionList` definition:
```python
yield SidebarOptionList(
    Option(_asset_type_label("instruction", plural=True), id="asset-type-instruction"),
    Option(_asset_type_label("command", plural=True), id="asset-type-command"),
    Option(_asset_type_label("skill", plural=True), id="asset-type-skill"),
    Option(_asset_type_label("agent", plural=True), id="asset-type-agent"),
    Option(_asset_type_label("mcp", plural=True), id="asset-type-mcp"),
    Option(_asset_type_label("pi-extension", plural=True), id="asset-type-pi-extension"),
    id="asset-types-list",
)
```

### 3.2 Event Handling & Keyboard Shortcuts
- `SidebarOptionList.BINDINGS` retains:
  ```python
  Binding("1", "asset_type('instruction')", "Instructions", show=False),
  Binding("2", "asset_type('command')", "Commands", show=False),
  Binding("3", "asset_type('skill')", "Skills", show=False),
  Binding("4", "asset_type('agent')", "Agents", show=False),
  Binding("5", "asset_type('mcp')", "MCPs", show=False),
  Binding("6", "asset_type('pi-extension')", "Pi Extensions", show=False),
  ```
- In `TUIApp.on_option_list_option_selected`:
  The guard `if not opt_id or opt_id.startswith("asset-type-separator"): return` remains safe as-is or can be preserved for backward safety.
- `TUIApp._show_asset_type`:
  Uses `asset_types_list.get_option_index(f"asset-type-{asset_type}")`. Since option IDs are unchanged, index lookup continues to work without adjustment.

### 3.3 Test Updates
- In `tests/test_tui/test_instruction_grid.py`:
  Lines 524-526 previously asserted that the second item was a disabled separator (`assert separator.disabled is True`).
  Update the test to assert:
  1. Option count is 6 (matching the 6 active asset types).
  2. None of the options are separators or disabled.
  3. Prompts match the plain plural names (`Instructions`, `Commands`, `Skills`, `Agents`, `MCPs`, `Pi Extensions`).
  4. First selectable option is `asset-type-instruction`.
- In `tests/test_tui/test_app_labels.py`:
  Verify options contain exact labels without number prefixes.

## 4. Verification & Testing
- Unit and TUI testing:
  - Run `uv run pytest -q tests/test_tui/test_instruction_grid.py tests/test_tui/test_app_labels.py tests/test_tui/test_sidebar_highlight_sync.py`
  - Run full test suite: `uv run pytest -q`
- Visual & functional verification:
  - Verify through automated headless Pilot test that all options render clean labels and highlight tracks active tab correctly.
