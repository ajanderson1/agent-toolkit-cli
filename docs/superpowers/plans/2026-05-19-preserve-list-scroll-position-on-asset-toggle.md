# Plan — Preserve list scroll position when toggling an asset

**Issue:** #87
**Spec:** [`../specs/2026-05-19-preserve-list-scroll-position-on-asset-toggle-design.md`](../specs/2026-05-19-preserve-list-scroll-position-on-asset-toggle-design.md)
**Approach:** Option A — save/restore `scroll_y` around `AssetGrid._rebuild()`.

## Pre-flight

- [ ] In worktree `.worktrees/fix-87-preserve-list-scroll-position-on-asset-toggle/`.
- [ ] `uv run pytest -q` is green on `HEAD`.

## Task 1 — Failing test (TDD)

**File:** `tests/test_tui/test_app.py`

Add a new pilot test `test_toggle_preserves_scroll_position_and_cursor`:

1. Build a doc with enough skill rows to overflow the terminal (e.g. 50 rows × 1 harness). Reuse `_doc()` style; parametrise row count or write a small helper.
2. Launch the app via `app.run_test(size=(80, 24))` (small terminal so the list scrolls).
3. Use the pilot to move the cursor partway down (e.g. press `Down` ~20 times) so `scroll_y > 0` and `cursor_coordinate.row` is mid-list.
4. Capture `before_scroll = table.scroll_y` and `before_cursor = table.cursor_coordinate`. Assert `before_scroll > 0` (proves the fixture actually scrolls — otherwise the test is vacuous).
5. Press `space` to toggle the current cell.
6. `await pilot.pause()` once (twice if needed — comment the second pause if added).
7. Assert `table.scroll_y == before_scroll` and `table.cursor_coordinate == before_cursor`.

**Run:** `uv run pytest tests/test_tui/test_app.py::test_toggle_preserves_scroll_position_and_cursor -q` — must **fail** before the fix.

## Task 2 — Fix

**File:** `src/agent_toolkit_tui/widgets/asset_grid.py`, function `_rebuild` (line 203).

Locate the existing cursor save (around line 208) and add a `scroll_y` save next to it. After all rows are re-added and the cursor is restored, restore `scroll_y` via `table.scroll_to(0, saved_scroll_y, animate=False)`.

Sketch (pseudocode — adapt to actual variable names in the file):

```python
def _rebuild(self) -> None:
    table = self.query_one(DataTable)
    saved_cursor = table.cursor_coordinate
    saved_scroll_y = table.scroll_y         # NEW
    table.clear(columns=True)
    # …existing rebuild logic (add columns, add rows)…
    # …existing cursor restore…
    table.scroll_to(0, saved_scroll_y, animate=False)   # NEW
```

Do **not** widen the change beyond these two lines. No other refactors.

## Task 3 — Re-run the new test

`uv run pytest tests/test_tui/test_app.py::test_toggle_preserves_scroll_position_and_cursor -q` must now pass. If a single `pilot.pause()` is not enough for `scroll_to` to land, add a second pause with a one-line comment explaining why (Textual reactive timing).

## Task 4 — Full suite

`uv run pytest -q` must be green. Pay attention to `test_space_toggles_cell_and_cursor_stays_in_place` (line 104) — it must still pass; if it regresses, the cursor-save logic was misordered.

## Task 5 — Manual smoke (verification artifact)

Capture a terminal recording or screenshot pair (before-toggle / after-toggle) showing the scroll position unchanged. Saved to `assets/verification/87/`.

A small Python script that drives the TUI via `app.run_test()` and dumps the visible table region before and after toggle is acceptable as the artifact — it does not need to be a real screen recording.

## Risks / gotchas

- `scroll_to(..., animate=False)` is fire-and-forget; if it does not land within one pause, the new test will tell us.
- If `saved_scroll_y` exceeds the new content height (e.g. after a filter change that removes rows), Textual should clamp. If the new test reveals it does not clamp, add a `min(saved_scroll_y, table.virtual_size.height - table.size.height)` style clamp.
- Out of scope: any change to filter-change / kind-change scroll behaviour beyond what the same save/restore happens to give us.

## Definition of done

- [ ] New test added and passing.
- [ ] Existing test still passing.
- [ ] `uv run pytest -q` green.
- [ ] Verification artifact saved under `assets/verification/87/`.
- [ ] Single conventional-commit message: `fix(#87): preserve scroll position when toggling asset`.
