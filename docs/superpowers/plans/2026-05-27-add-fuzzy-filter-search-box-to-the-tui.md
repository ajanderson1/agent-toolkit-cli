# Plan — Add fuzzy-filter search box to the TUI (#249)

Spec: `docs/superpowers/specs/2026-05-27-add-fuzzy-filter-search-box-to-the-tui-design.md`

TDD throughout: write the failing test for each behaviour, watch it fail for
the right reason, implement, watch it pass. Run `uv run pytest -q tests/test_tui`
after each phase.

## Files touched

- `src/agent_toolkit_tui/widgets/skill_grid.py` — filter input, filtered view,
  index remap, Down/Tab escape.
- `src/agent_toolkit_tui/app.py` — focus filter on open; `slash` re-focus binding.
- `src/agent_toolkit_tui/css/app.tcss` — filter input styling.
- `tests/test_tui/test_skill_grid_filter.py` — new test file (9 tests).

## Phase 1 — Filtered view in `SkillGrid` (no UI yet)

Pure-logic core first; lets the remap tests run without keyboard plumbing.

1. **Test (red):** `test_visible_rows_substring`, `test_visible_rows_case_insensitive`,
   `test_row_count_unaffected_by_filter`. Construct `SkillGrid([_row("alpha"),
   _row("beta"), _row("gamma")])`, set `grid._filter` directly (or via a new
   `set_filter`), mount in a host app, assert `_visible_rows()` slugs and that
   `row_count == 3` regardless.
2. **Implement:**
   - Add `self._filter: str = ""` in `__init__`.
   - Add `set_filter(self, text: str) -> None` that lowercases+strips, stores,
     and rebuilds the table (guarded for pre-mount as the other mutators are).
   - Add `_visible_rows(self) -> list[SkillRow]`: filtered when `self._filter`,
     else `list(self._rows)`.
   - `_rebuild()`: iterate `self._visible_rows()`; compute `max_row` from the
     visible length.
   - Remap cursor-indexed sites to a single resolved visible list:
     `action_info`, `_toggle_at`, `_context_for` — replace `self._rows` /
     `len(self._rows)` with the visible list. (`action_toggle_column`,
     `row_count`, `row_slugs` stay on `self._rows` per spec.)
3. **Green:** phase-1 tests pass; full `tests/test_tui` still green
   (no regression to existing grid tests, which use no filter).

## Phase 2 — Filter input widget + change wiring

1. **Test (red):** `test_filter_box_renders` (mount `TUIApp`, `#skill-filter`
   exists and is an `Input`), `test_typing_narrows_rows` (type into the input
   via `pilot`, assert visible rows shrink), `test_toggle_after_filter_targets_visible_row`
   (filter, move into table, `space`, pending key is the visible slug),
   `test_all_ignores_filter` (filter hides one row, press `a`, pending covers
   all linkable rows).
2. **Implement:**
   - `compose()`: yield `Input(placeholder="filter…", id="skill-filter")`
     before the `DataTable`.
   - `on_input_changed`: if `event.input.id == "skill-filter"` →
     `self.set_filter(event.value)`.
   - `on_input_submitted`: if it's the filter → focus `#skill-table`.
3. **Green.**

## Phase 3 — Focus + Down/Tab escape

1. **Test (red):** `test_focus_starts_in_filter` (after mount, `app.focused`
   is `#skill-filter`), `test_down_moves_focus_to_table`,
   `test_tab_moves_focus_to_table` (focus filter, press key, `app.focused` is
   `#skill-table`).
2. **Implement:**
   - `FilterInput(Input)` subclass in `skill_grid.py` with
     `def on_key(self, event)`: if `event.key in ("down", "tab")` → query the
     sibling `#skill-table` (via `self.screen` / `self.app`), `.focus()`,
     `event.stop()` and `event.prevent_default()`. Use this subclass in
     `compose()`.
   - `TUIApp.on_mount`: focus `#skill-filter` instead of `#skill-table`
     (keep the `try/except` guard).
   - `TUIApp`: add `Binding("slash", "focus_filter", "Filter", priority=True)`
     and `action_focus_filter` → focus `#skill-filter` (guarded).
3. **Green.**

## Phase 4 — Styling + manual smoke

1. Add to `css/app.tcss`:
   `SkillGrid Input#skill-filter { height: 3; border: round $primary 30%; margin: 0 1 1 1; }`
2. Smoke: `uv run agent-toolkit-tui --version` (cheap import/exec check;
   full interactive run is the Step 9 verify recipe).

## Phase 5 — Full suite + verify

1. `uv run pytest -q` — all green (baseline was 448 passed, 2 skipped; expect
   +9).
2. Step 9 verify: terminal recipe — `agent-toolkit-tui --version` captured to
   `run.log` (TUI has no `--help`; version is the non-interactive entry-point
   check). The 9 pilot tests are the real behavioural proof.

## Notes / guards

- `_row()` test helper: copy the one in `test_status_counters.py`
  (`SkillRow` + `SkillCell` over `INTERACTIVE_AGENTS`).
- Keep `priority=True` off the filter's own keys — the `FilterInput.on_key`
  handles Down/Tab locally; everything else (letters) must reach the input as
  text, so do **not** add App-level letter bindings that would steal them
  while the filter is focused. (The existing App bindings `s`, `i`, `q` use
  plain letters — verify in Phase 3 that typing those into the focused filter
  inserts text rather than firing the binding. Textual routes key events to
  the focused widget first; an `Input` consumes printable keys, so bindings
  should not fire. If a test shows otherwise, that is a real bug to fix, not
  to paper over.)
