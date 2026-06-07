# Plan — Preserve view pane position on checkbox toggle (#321)

Spec: `docs/superpowers/specs/2026-06-07-preserve-view-pane-design.md`

Shared fix across 4 grids' `_rebuild`. TDD: failing scroll-preservation test
first (against skill_grid, the richest), then the edit in all four grids.

## Task 1 — failing test first

Add `tests/test_tui/test_view_pane_preservation.py` (or extend an existing grid
test). App-level Pilot test using a real grid with many rows:

- Build a `SkillGrid` with ~40 rows (enough to overflow the viewport) mounted
  in a small test App (constrained height so the DataTable scrolls).
- `await pilot.pause()`; scroll down: set `table.scroll_y` to a mid value (or
  `table.scroll_to(y=N, animate=False)`), pause.
- Move cursor to a row that's currently mid-pane.
- Record `table.scroll_y` and `table.cursor_coordinate`.
- Press `space` (toggle the cell) → `_rebuild` runs.
- Assert `table.scroll_y == recorded_scroll_y` (the viewport did not jump) and
  `table.cursor_coordinate.row == recorded_row`.

Run → fails (current `_rebuild` resets scroll to 0 on clear).

NOTE on test realism: Textual scroll only engages when the DataTable's content
height exceeds its container. The test App must give the grid a fixed small
height (CSS `height: 10` or similar) and enough rows. If headless scroll proves
flaky in `run_test()`, fall back to asserting on `scroll_target_y` / driving
`table.scroll_to` then reading back after rebuild — but prefer the real
`scroll_y` round-trip.

## Task 2 — fix `_rebuild` in all four grids

Identical edit in each `_rebuild`:

```python
def _rebuild(self, table: DataTable) -> None:
    saved = table.cursor_coordinate
    saved_scroll = (table.scroll_x, table.scroll_y)   # NEW
    table.clear(columns=True)
    ... (unchanged column + row adds) ...
    if <rows>:
        table.cursor_coordinate = Coordinate(...)
    # NEW: pin the viewport back after the cursor is set (cursor-set can
    # auto-scroll; restoring last wins). Clamped by Textual to valid range.
    table.scroll_to(
        x=saved_scroll[0], y=saved_scroll[1], animate=False, force=True
    )
```

Files (same pattern, mind the differing column counts in the cursor clamp —
leave those untouched, only add the scroll save/restore):
- `src/agent_toolkit_tui/widgets/skill_grid.py:543` `_rebuild`
- `src/agent_toolkit_tui/widgets/agent_grid.py:273` `_rebuild`
- `src/agent_toolkit_tui/widgets/pi_grid.py` `_rebuild` (~line 286)
- `src/agent_toolkit_tui/widgets/instruction_grid.py:320` `_rebuild`

Keep the scroll-restore OUTSIDE the `if <rows>:` block so it also runs (harmless,
clamps to 0) when the grid is empty — but guard it inside the try if `_rebuild`
is wrapped. Each grid's `_rebuild` is called with the table in hand, so no extra
query needed.

## Task 3 — verify

- `uv run pytest tests/test_tui/test_view_pane_preservation.py -q` green.
- `uv run pytest -q` full suite green (no regression — cursor clamp + all
  existing toggle/apply tests unaffected; scroll restore is additive).
- Headless smoke → `assets/verification/321/run.log` showing scroll_y preserved
  across a toggle.

## Risks / notes

- **Cursor auto-scroll vs scroll restore ordering** — restore scroll AFTER
  setting cursor, else the cursor-set scroll wins. This is the load-bearing
  detail; the test guards it.
- **`force=True`** needed so `scroll_to` doesn't no-op when it thinks it's
  already at target after the clear.
- **Headless scroll flakiness** — DataTable must actually overflow its
  container in the test or scroll_y stays 0 and the test is vacuous. Give the
  test App a fixed small height and enough rows; assert the precondition
  (scroll_y > 0 before toggle) so a vacuous pass is impossible.
- **`set_rows`/`set_scope` callers** — they also go through `_rebuild` and will
  now preserve scroll; this is acceptable/beneficial (refresh no longer jumps).
  Filtering resets via its own path and lands clamped — out of scope, not broken.
- Shared 4-grid edit → a frontend-races/Textual-timing self-review pass is
  warranted (ce-julik-frontend-races-reviewer).
