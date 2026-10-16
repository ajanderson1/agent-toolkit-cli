# Clean Asset Types Sidebar Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove divider lines and numeric prefixes from `#asset-types-list` in the left sidebar of `agent-toolkit-tui`, displaying only clean plural asset type names (e.g. "Instructions", "Commands", "Skills", "Agents", "MCPs", "Pi Extensions").
**Architecture:** Update `SidebarOptionList` option declarations in `TUIApp.compose()` (`src/agent_toolkit_tui/app.py`) to omit separator options and render `_asset_type_label(asset_type, plural=True)` directly while preserving option IDs and keyboard bindings. Update corresponding tests in `tests/test_tui/test_instruction_grid.py` and `tests/test_tui/test_app_labels.py`.
**Tech Stack:** Python 3.12+, Textual, pytest, uv.
**Spec:** `docs/specs/2026-10-16-526-clean-asset-types-sidebar.md`

## Global Constraints
- Python 3.12+ compatibility.
- Do not alter the order of asset types in the sidebar: `instruction`, `command`, `skill`, `agent`, `mcp`, `pi-extension`.
- Preserve existing option IDs (`asset-type-instruction`, `asset-type-command`, `asset-type-skill`, `asset-type-agent`, `asset-type-mcp`, `asset-type-pi-extension`) to ensure all highlight synchronization and click selection logic continues functioning unchanged.
- Preserve 1–6 keyboard bindings on `SidebarOptionList` (`show=False`) for keyboard switching.
- All existing tests across the entire project must pass cleanly without polluting the developer's real environment.

## Review Focus
- Sidebar option prompts: verify no numeric prefixes (`1 - `, `[dim]...[/dim]`) remain.
- Separators: verify no separator options or horizontal rule characters remain in `#asset-types-list`.
- Option count: verify `#asset-types-list.option_count` equals 6.
- Highlight sync: verify `_show_asset_type` properly highlights the active option on mount and on tab switch.
- Regression: verify all asset tab switches (`action_asset_type`) and sidebar click events operate identically.

---

### Task 1: Update test expectations for sidebar options (RED)

**Files:**
- Modify: `tests/test_tui/test_instruction_grid.py`
- Modify: `tests/test_tui/test_app_labels.py`

**Interfaces:**
- Consumes: `TUIApp`, `OptionList`
- Verifies: Sidebar option count, option prompts, option IDs, absence of separators

- [ ] **Step 1: Update `tests/test_tui/test_instruction_grid.py`**
  Update `test_sidebar_lists_all_asset_types_with_instruction_first()`:
  - Remove assertions expecting index 1 to be a disabled separator.
  - Assert `ol.option_count == 6`.
  - Assert none of the options are disabled.
  - Assert prompts match exact clean labels: `["Instructions", "Commands", "Skills", "Agents", "MCPs", "Pi Extensions"]`.
  - Assert option IDs match `["asset-type-instruction", "asset-type-command", "asset-type-skill", "asset-type-agent", "asset-type-mcp", "asset-type-pi-extension"]`.

- [ ] **Step 2: Update `tests/test_tui/test_app_labels.py`**
  Add explicit assertion that no numeric prefixes (`-` or digits) appear in the prompts:
  `assert all(not opt.startswith(f"{i}") for i in range(10) for opt in labels)`
  and `assert all(" - " not in opt for opt in labels)`.

- [ ] **Step 3: Run test suite to verify RED**
  Run: `uv run pytest -q tests/test_tui/test_instruction_grid.py tests/test_tui/test_app_labels.py`
  Expected: FAIL due to existing separators and numbered prefixes in `TUIApp.compose()`.

---

### Task 2: Clean sidebar option list in `src/agent_toolkit_tui/app.py` (GREEN)

**Files:**
- Modify: `src/agent_toolkit_tui/app.py`

**Interfaces:**
- Consumes: `_asset_type_label`, `SidebarOptionList`, `Option`
- Produces: Clean `#asset-types-list` with 6 options and zero separators

- [ ] **Step 1: Update `TUIApp.compose()`**
  Replace lines 394–404 in `src/agent_toolkit_tui/app.py` with:
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

- [ ] **Step 2: Run targeted test suite to verify GREEN**
  Run: `uv run pytest -q tests/test_tui/test_instruction_grid.py tests/test_tui/test_app_labels.py tests/test_tui/test_sidebar_highlight_sync.py`
  Expected: PASS.

---

### Task 3: Full test suite verification & evidence collection

**Files:**
- Output: `assets/verification/526/manifest.md`
- Output: `assets/verification/526/climb.txt`

- [ ] **Step 1: Run climb command**
  Run: `uv run pytest -q tests/test_tui/test_instruction_grid.py tests/test_tui/test_app_labels.py tests/test_tui/test_sidebar_highlight_sync.py`
  Record exit code 0.

- [ ] **Step 2: Run full pytest suite**
  Run: `uv run pytest -q`
  Record exit code 0.
