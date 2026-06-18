# All Asset Pane Filters Design

## Issue

GitHub: https://github.com/ajanderson1/agent-toolkit-cli/issues/458

## Problem

The Textual TUI has a search/filter box only on the Skills pane. Users can narrow skill rows by slug and move from the filter into the table with Down, Tab, or Enter, but the Instructions, Commands, Pi Extensions, Agents, and MCPs panes expose only their tables. That inconsistency breaks muscle memory and makes non-skill panes harder to scan as asset counts grow.

## Goals

- Add a filter input above every asset-type table: Instructions, Commands, Pi Extensions, Agents, and MCPs.
- Preserve the existing Skills pane behavior and keyboard contract.
- Filter each pane by case-insensitive substring match on row slug.
- Keep row count, footer/status math, and bulk column actions based on the full row set, not the filtered view.
- Make row-targeted actions use the visible filtered row under the cursor.
- Make `/` focus the active pane's filter instead of always focusing `#skill-filter`.
- Treat zero-match filtered tables as safe empty views: no crashes, and row actions no-op.
- Cover at least one non-skill pane and app-level `/` routing with tests, while leaving room for shared regression tests across all grids.

## Non-goals

- Changing the filter algorithm beyond case-insensitive slug substring matching.
- Adding fuzzy search, highlights, sorting, cross-pane search, or saved filters.
- Changing asset-type navigation, sidebar behavior, scope toggling, apply/discard/revert behavior, or pending-operation semantics.
- Refactoring all grid widgets into a shared base class.
- Changing CLI output or data model row structures.

## Existing behavior to preserve

`src/agent_toolkit_tui/widgets/skill_grid.py` already defines the contract:

- `FilterInput` intercepts Down and Tab, focuses `#skill-table`, and stops the key event.
- `SkillGrid.compose()` renders `#skill-filter` above `#skill-table`.
- `set_filter()` lowercases and trims input, then rebuilds the table.
- `_visible_rows()` filters `self._rows` by slug and never mutates full row state.
- `on_input_changed()` updates the filter as the user types.
- `on_input_submitted()` focuses the table when the user presses Enter.
- `_rebuild()` iterates visible rows only, clamps cursor position to the visible table, and preserves scroll offset where possible.
- Row-targeted actions (`_toggle_at`, `action_info`, `_context_for`, `cursor_to_cell`) map cursor row indexes through `_visible_rows()`.
- Column/bulk actions intentionally iterate `self._rows` so hidden rows remain in scope for All/None semantics.

The implementation should copy this behavior deliberately, not invent a second filter contract.

## Design

### Shared filter input widget

Create a small shared widget module, `src/agent_toolkit_tui/widgets/filter_input.py`, containing a reusable `GridFilterInput`. It should accept the table selector it hands focus to on Down/Tab. This extracts the only behavior that is truly identical across grids while avoiding a broad base-class refactor.

The Skills pane can either keep its existing `FilterInput` for compatibility during the first pass or switch to `GridFilterInput(table_selector="#skill-table", id="skill-filter")`. Switching Skills is preferred if tests stay green, because there should be one keyboard-focus implementation.

### Per-grid filter state

Each asset grid owns its own filter string and table rebuild because each grid has different columns, cell state, info modal context, and pending key shape.

For every grid widget:

| Grid | Filter ID | Table ID | Row type |
|---|---|---|---|
| `InstructionGrid` | `instruction-filter` | `instruction-table` | `InstructionRow` |
| `CommandGrid` | `command-filter` | `command-table` | `CommandRow` |
| `PiGrid` | `pi-filter` | `pi-table` | `PiExtensionRow` |
| `AgentGrid` | `agent-filter` | `agent-table` | `AgentRow` |
| `McpGrid` | `mcp-filter` | `mcp-table` | `McpRow` |
| `SkillGrid` | `skill-filter` | `skill-table` | `SkillRow` |

Each grid should add:

- `self._filter: str = ""` in `__init__`.
- `set_filter(self, text: str) -> None`, matching Skills semantics.
- `_visible_rows(self) -> list[RowType]`, matching Skills semantics.
- `on_input_changed()` branch for that grid's filter ID.
- `on_input_submitted()` branch that focuses that grid's table.
- `compose()` yielding the filter input before the table.

### Visible-row action mapping

Every row-targeted path must use `_visible_rows()` for cursor row indexes:

- `action_toggle_cell()` delegates to `_toggle_at(table.cursor_coordinate)` as today; `_toggle_at()` must choose `row = visible[coord.row]`.
- `action_info()` must check `coord.row >= len(visible)` and use `row = visible[coord.row]` before building info context.
- `_context_for(..., row_index=...)` must map `row_index` through visible rows when it returns row-specific context.
- Any `cursor_to_cell()` helper should look up the slug in visible rows before setting `cursor_coordinate`.
- `_rebuild()` must iterate visible rows and clamp the cursor only when visible rows exist. With no matches, the table remains empty and row actions return early.

Bulk actions keep the current full-row behavior. Existing `action_toggle_column()` loops over `self._rows`; that must remain true so All/None means “all rows in this asset pane,” not “only visible rows.”

### App-level `/` routing

`TUIApp.action_focus_filter()` should map `self._asset_type` to the active pane's filter ID and focus that `Input`:

- `instruction` → `#instruction-filter`
- `skill` → `#skill-filter`
- `command` → `#command-filter`
- `pi-extension` → `#pi-filter`
- `agent` → `#agent-filter`
- `mcp` → `#mcp-filter`

If the selected pane has not mounted or the filter cannot be found, the action should no-op like current defensive focus paths. This keeps `/` safe during startup and tests.

`on_mount()` may keep focusing the Skills filter on launch because Skills remains the default active pane. If the project later changes the default asset type, `on_mount()` should focus through `action_focus_filter()` instead.

## Acceptance criteria

1. Every asset-type pane renders one filter input above its table.
2. Every filter uses case-insensitive substring matching on row slug.
3. Empty filter shows all rows.
4. `row_count`, content header item counts, footer pending counts, and apply/discard logic continue to use the full row set.
5. Pending operations survive filter changes and continue rendering when the matching row becomes visible again.
6. Down, Tab, and Enter from a filter focus that pane's table.
7. `/` focuses the active pane's filter for Skills, Instructions, Commands, Pi Extensions, Agents, and MCPs.
8. Row-targeted toggles and info actions use the visible row under the cursor when a filter is active.
9. Bulk column actions continue to act on all rows, including hidden rows.
10. Zero-match filters render an empty table without crashing; row actions no-op.
11. Existing Skills filter tests still pass.
12. New tests cover at least one non-skill pane for visible rows, zero-match safety, cursor-target behavior, and focus handoff.
13. New app tests cover `/` focus routing after switching active asset type.

## Test surface

- Existing Skills contract: `uv run pytest tests/test_tui/test_skill_grid_filter.py -q`
- New non-skill grid filter tests, preferably `tests/test_tui/test_asset_grid_filters.py` or per-grid additions under existing grid test files.
- App focus routing: `tests/test_tui/test_app.py` or a focused `tests/test_tui/test_app_filter_focus.py`.
- Full TUI regression: `uv run pytest tests/test_tui -q`

## Implementation notes

- Prefer small per-widget edits over a new shared base class. The grids are similar but not identical; a base class would hide row-key and info-context differences.
- Keep filter IDs stable and predictable. Tests and `/` routing should use the IDs listed in this document.
- Use existing row factory helpers in grid tests where present (`_full_row`, `_linked_row`, `_unlinked_row`) instead of creating duplicate fixtures.
- If adding one shared test helper, keep it in tests only. Do not let test abstraction force production abstraction.
- Preserve `DataTable.clear(columns=True)` and current column order in each grid.
- Keep all filter behavior inside TUI widget code; CLI commands should not learn about active filters.

## Open questions resolved

- Filter scope is slug only, not source/ref/state/harness columns.
- Bulk All/None actions apply to the full row set, not the visible subset.
- Zero-match views should be safe empty tables; no placeholder row required.
- `/` should route by active asset type, not focused widget ancestry.
