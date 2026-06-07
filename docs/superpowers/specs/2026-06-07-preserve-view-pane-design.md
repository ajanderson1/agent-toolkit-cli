# Design — Preserve view pane position on checkbox toggle (#321)

**Issue:** #321 · **Type:** fix · **Mode:** `--auto` · **Date:** 2026-06-07

## Problem

Toggling a checkbox cell in any TUI grid jumps the view pane: the scroll
position shifts so the toggled item moves on screen. Toggling is a single-item
state change and should not move the viewport at all.

## Root cause

Every grid widget (`skill_grid`, `agent_grid`, `pi_grid`, `instruction_grid`)
implements `_rebuild(table)` the same way:

```python
saved = table.cursor_coordinate      # only the CURSOR is saved
table.clear(columns=True)            # <-- this resets scroll_y/scroll_x to 0
... re-add columns + rows ...
table.cursor_coordinate = Coordinate(row=..., column=...)  # may auto-scroll cursor into view
```

`DataTable.clear()` resets the scroll offset to the top. The save/restore only
covers `cursor_coordinate`, never `scroll_y`/`scroll_x`. So after a toggle
(which calls `_rebuild`), the viewport snaps to the top (or wherever the cursor
forces it), visibly jumping the pane. The cursor restore can *partly* mask this
when the cursor is near the top, but for a mid-pane item the whole pane shifts.

This is a **shared bug across all four grids** — the toggle path
(`_toggle_at` / `action_toggle_column` → `_rebuild`) is identical in each.

## Fix

In each grid's `_rebuild`, also save and restore the scroll offset around the
clear+rebuild:

```python
saved = table.cursor_coordinate
saved_scroll_x, saved_scroll_y = table.scroll_x, table.scroll_y
table.clear(columns=True)
... re-add columns + rows ...
table.cursor_coordinate = Coordinate(...)            # set cursor first
table.scroll_to(x=saved_scroll_x, y=saved_scroll_y,  # then pin the viewport
                animate=False, force=True)
```

- `scroll_to(..., animate=False, force=True)` sets the offset immediately (no
  animation, force past the "already at target" short-circuit). Restoring AFTER
  setting `cursor_coordinate` is essential: setting the cursor can trigger an
  auto-scroll-to-cursor that would otherwise win.
- Verified API on Textual 8.2.5: `scroll_x`/`scroll_y` (current offset),
  `scroll_to(x, y, *, animate, force, immediate)`.
- The restored offset is clamped by Textual to the new content's max scroll, so
  if the rebuild shortened the list the offset can't exceed valid range (no
  manual clamp needed; `scroll_to` handles it).

## Scope of change

Four `_rebuild` methods, one identical edit each:
- `src/agent_toolkit_tui/widgets/skill_grid.py`
- `src/agent_toolkit_tui/widgets/agent_grid.py`
- `src/agent_toolkit_tui/widgets/pi_grid.py`
- `src/agent_toolkit_tui/widgets/instruction_grid.py`

No change to toggle logic, pending state, or cursor restore — purely additive
viewport preservation.

## Out of scope (from issue)

Other causes of view-pane movement — filtering, selection changes, resize.
This is strictly the checkbox-toggle side effect. (Filtering legitimately
changes the visible set and *should* reset scroll; we only preserve scroll on a
toggle-driven rebuild, not on `set_rows`/`set_scope` which are content changes.
See note below.)

### Note: which `_rebuild` callers should preserve scroll?

`_rebuild` is called from: `_toggle_at`, `action_toggle_column`,
`clear_pending`, `restore_pending` (toggle-adjacent — preserve scroll), AND
`set_rows`/`set_scope` (content/scope changes — scroll reset is acceptable, the
content changed). The simplest correct fix puts the save/restore *inside*
`_rebuild`, so it applies to all callers. That is fine: on `set_rows` the saved
offset is clamped to the new (possibly empty) content, and for a refresh that
returns the same rows it correctly preserves position too (a bonus — `ctrl+r`
refresh no longer jumps either). Preserving scroll on a same-content rebuild is
never wrong; the only case where a reset is "expected" is a filter narrowing,
which goes through the filter handler's own rebuild and will simply land at a
clamped offset — acceptable and not in this issue's scope.

## Definition of done (from issue)

- [x] Toggling a checkbox on/off does not scroll or move the view pane.
- [x] The toggled item stays in the same on-screen position across the toggle.
- [x] Scroll offset / selection is preserved through the toggle (cursor was
  already preserved; this adds scroll-offset preservation).

## Verification

- New Pilot test per the shared behavior: build a grid with enough rows to
  scroll, scroll down (set `scroll_y`), move the cursor to a mid-pane row,
  toggle the cell (`space`), assert `table.scroll_y` is unchanged (within a
  tolerance for clamping) AND the cursor row is unchanged.
- Test at least one representative grid end-to-end (skill_grid, the richest);
  add a lighter assertion for the others or a parametrized test.
- Full suite green; existing grid tests unaffected.
- Headless smoke into `run.log` showing scroll_y preserved across a toggle.
