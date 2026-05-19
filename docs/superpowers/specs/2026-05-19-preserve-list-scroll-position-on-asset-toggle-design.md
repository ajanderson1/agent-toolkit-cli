# Spec — Preserve list scroll position when toggling an asset

**Issue:** #87
**Type:** fix
**Date:** 2026-05-19

## Goal

When the user toggles an asset on/off in the TUI's harness grid view, the displayed list must not visually jump. Scroll offset and cursor row remain unchanged across the toggle; only the affected cell's state indicator updates.

## Context

The TUI grid (`src/agent_toolkit_tui/widgets/asset_grid.py`) renders assets in a Textual `DataTable`. Every mutating action — including a single-cell toggle — currently invokes `AssetGrid._rebuild()` (line 203), which calls `table.clear(columns=True)` and then re-adds all columns and rows from scratch. `clear(columns=True)` resets `scroll_y` to `0.0`, so a user who has scrolled partway down a long list is yanked back to the top on every keystroke. The cursor row is restored, but the visible window is not.

Mutating callers that trigger `_rebuild()`:

- `_toggle_at` (line 194) — single cell toggle, the common case in this bug.
- `action_toggle_column` (line 167) — bulk toggle of a column.
- `set_kind` / `set_scope` (lines 73, 77) — filter changes.
- `update_state` (line 84) — external state refresh.
- `clear_pending` (line 91) — discard pending changes.
- `on_input_changed` (line 61) — filter text update.

The bug is most painful for single-cell toggles, which dominate the user's workflow. Filter changes and bulk operations are less frequent and a scroll reset there is arguably expected.

## Existing test pattern

`tests/test_tui/test_app.py::test_space_toggles_cell_and_cursor_stays_in_place` (line 104) already asserts `table.cursor_coordinate` survives a toggle. It does **not** assert `scroll_y`, and its fixture has too few rows to scroll. The new test extends this pattern with a long fixture and an additional `scroll_y` assertion.

## Approach — chosen

**Option A: save and restore `scroll_y` around `_rebuild()`.**

In `_rebuild()`:
1. Before `table.clear(columns=True)`, capture `saved_scroll = table.scroll_y` alongside the existing cursor save.
2. After all rows have been added and the cursor restored, call `table.scroll_to(0, saved_scroll, animate=False)` (or `set_scroll`) to restore the offset.
3. Apply on every `_rebuild()` call, not just the toggle paths. Filter changes scrolling back to top would be a separate, smaller question; preserving offset across all mutations is simpler and more consistent.

### Why A over B (in-place cell update)

Option B (update only the toggled cell via `DataTable.update_cell`) is asymptotically nicer (O(1) per toggle vs O(N) full rebuild) and avoids any flicker. But it requires splitting `_rebuild()` into a partial-update path and a full-rebuild path, with care around what state changes really need a full rebuild (filter text, kind/scope changes still do). For a v1 fix on a small data set, the rebuild cost is invisible. Option A is a 2-3 line change with a tight test; Option B is a refactor with a wider blast radius. We pick A and revisit B only if profiling shows the rebuild is actually slow.

### Why A over C (`move_cursor(scroll=False)`)

C is a cleaner cursor-restoration idiom but does not address the underlying scroll reset; it would still need the `scroll_y` save/restore from A. So C is a small style improvement layered on A. Skip for this fix; can be a follow-up cleanup if desired.

## Out of scope

- Refactoring `_rebuild()` into partial-update vs full-rebuild paths (Option B).
- Replacing direct `cursor_coordinate` assignment with `move_cursor` (Option C).
- Scroll-preservation semantics for filter/kind/scope changes (we preserve them too, but no UX-design decision is made about whether that's *desirable* — it is at minimum consistent and not worse).
- Any other TUI widgets.

## Definition of done

- `_rebuild()` preserves `scroll_y` across all mutations.
- A new pilot test in `tests/test_tui/test_app.py` seeds enough rows to scroll, scrolls partway down, toggles a cell, and asserts both `cursor_coordinate` **and** `scroll_y` are unchanged.
- The existing test `test_space_toggles_cell_and_cursor_stays_in_place` still passes.
- `uv run pytest -q` is green.
- Manual smoke per issue's repro confirms the list no longer jumps on toggle.

## Risks

- `DataTable.scroll_y` is a Textual reactive; `scroll_to(..., animate=False)` may need one `await pilot.pause()` to land. The test will reveal this.
- If the saved `scroll_y` exceeds the new content height (because rows were filtered out), `scroll_to` should clamp to the max — verify Textual does this; otherwise clamp manually.
