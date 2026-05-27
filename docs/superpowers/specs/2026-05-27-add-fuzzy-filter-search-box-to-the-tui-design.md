# Design — Add fuzzy-filter search box to the TUI (#249)

## Problem

The v1 TUI had a filter box at the top: it received focus on open, typing
narrowed the skill list, and Down/Tab dropped focus into the main pane to
select a skill. The current (v2) TUI lost that box during the rewrite to the
skill-only cockpit. Bring it back.

## Goal

A filter text box at the top of the TUI that:

1. Renders above the skill grid.
2. Holds focus when the TUI opens.
3. Filters the visible skill rows as you type (case-insensitive substring on
   the skill slug — the same matching v1 used).
4. Drops focus into the main pane (the `#skill-table` DataTable) on **Down**
   or **Tab**, so the user can then select a skill.

## Out of scope

- **Matching algorithm.** Reuse case-insensitive substring matching on the
  slug (`filter in slug.lower()`), exactly as v1 did. No fuzzy-ranking
  library, no scoring. The issue explicitly fences this off.
- Filtering on columns other than the slug (source, state, agent names).
- Persisting the filter text across refresh/scope-toggle.

## Approach

The current grid widget is `SkillGrid(Vertical)` containing a single
`DataTable#skill-table`. It stores `self._rows` (sorted) and `_rebuild()`
renders every row. We introduce a filter without changing the matching
semantics:

### 1. Filter input lives in `SkillGrid`

Mirror v1's placement: the `Input` is a child of the grid widget, composed
above the table, so the widget owns both the filter state and the rows it
filters.

- `compose()` yields `Input(placeholder="filter…", id="skill-filter")` then
  the existing `DataTable#skill-table`.
- New widget state: `self._filter: str = ""`.

### 2. Filtered view

Add `_visible_rows() -> list[SkillRow]` returning `self._rows` narrowed by the
filter:

```python
if self._filter:
    return [r for r in self._rows if self._filter in r.slug.lower()]
return list(self._rows)
```

`_rebuild()` iterates `_visible_rows()` instead of `self._rows`. Everything
that maps a cursor row index back to a row (`action_info`, `_toggle_at`,
`action_toggle_column`, `_context_for`, status rollup) must resolve against
the **same visible list**, not `self._rows`, so the cursor never points at a
hidden row.

- `row_count` / `row_slugs` continue to report **all** rows (these feed the
  content-header "N items" and the apply/status math, which operate over the
  full set, not the filtered view). The filter is a view concern; pending
  state and counts stay whole.
- Toggling a column (`a`) acts on **all** rows, regardless of the active
  filter. The filter is purely a view over the rows; "All/None" stays a
  whole-column operation so the filter never silently changes what an apply
  would touch. `action_toggle_column` keeps iterating `self._rows`. (A user
  who wants to limit the toggle scope clears the filter or toggles cells
  individually.)

### 3. Filter events

On the `SkillGrid`:

- `on_input_changed(Input.Changed)`: if `event.input.id == "skill-filter"`,
  set `self._filter = event.value.strip().lower()` and rebuild the table.
- `on_input_submitted(Input.Submitted)` (Enter): move focus to
  `#skill-table` — a convenience escape, same as v1.

### 4. Focus wiring (the new behaviour)

Two pieces the v1 box didn't fully have:

- **Focus on open.** `TUIApp.on_mount` currently focuses `#skill-table`.
  Change it to focus `#skill-filter` instead, so the cursor lands in the box.
- **Down / Tab escape from the box.** Add an `Input`-level key handler on the
  filter so that Down-arrow or Tab moves focus into `#skill-table`. Implement
  via `on_key` on a small `Input` subclass (`FilterInput`) — checking
  `event.key in ("down", "tab")`, focusing the table, and calling
  `event.stop()`/`event.prevent_default()` so Tab does not run Textual's
  default focus-cycle (which could land somewhere unpredictable) and Down does
  not insert into the field. Up-arrow is left to default (no row above the
  box).

A `slash` binding to re-focus the filter (as v1 had) is a nice-to-have but
**not required by the DoD**; include it since it is cheap and restores muscle
memory — `Binding("slash", "focus_filter", "Filter")` on the App, focusing
`#skill-filter`.

### 5. Styling

Add CSS so the input reads as a compact top bar, matching v1's treatment:

```
SkillGrid Input#skill-filter { height: 3; border: round $primary 30%; margin: 0 1 1 1; }
```

(`SkillGrid` already sets `border: round $primary` on itself and
`height: 1fr` on its DataTable; the input slots above the table.)

## Definition of done (from the issue)

- [x] A filter text box renders at the top of the TUI.
- [x] Focus starts in the filter box on open.
- [x] Typing filters the skill list in the main pane.
- [x] Down or Tab from the filter box moves focus into the main pane.

## Testing strategy (TDD)

All tests use Textual's `App.run_test()` pilot harness, matching
`tests/test_tui/test_status_counters.py`.

New file `tests/test_tui/test_skill_grid_filter.py`:

1. **renders filter box** — mount `TUIApp`, assert `#skill-filter` exists and
   is an `Input`.
2. **focus starts in filter** — after mount, `app.focused` is the
   `#skill-filter` input (not the table).
3. **typing narrows rows** — grid with slugs `["alpha", "beta", "gamma"]`;
   set filter to `"a"` (or type via the input) → visible rows are those whose
   slug contains `a`; set to `"beta"` → only `beta`; clear → all three.
4. **filter is case-insensitive** — `"BETA"` matches `beta`.
5. **Down moves focus to table** — focus the filter, `pilot.press("down")`,
   assert `app.focused` is `#skill-table`.
6. **Tab moves focus to table** — focus the filter, `pilot.press("tab")`,
   assert `app.focused` is `#skill-table`.
7. **row_count unaffected by filter** — full count stays N while the visible
   view is narrowed (guards the content-header / status math).
8. **toggle after filter targets a visible row** — filter to one slug, move
   into the table, `space`, assert the pending entry is for the visible slug
   (guards the index→row remap).
9. **"All" ignores the filter** — grid with 3 slugs, set a filter that hides
   one, press `a` on an agent column → pending entries cover **all** rows that
   the column can link (not just the visible ones). Guards the design
   decision that "All/None" stays whole-column.

## Risks

- **Cursor index drift** is the main hazard: every place that does
  `self._rows[coord.row]` must switch to the visible list. Test 8 guards the
  toggle path; the plan must enumerate each call-site so none is missed.
  Enumerated call-sites (verified against current `skill_grid.py`):
  - **Switch to visible rows** (cursor-indexed — must resolve against what's
    shown): `action_info` (`coord.row` bounds + `self._rows[coord.row]`),
    `_toggle_at` (same), `_context_for` (`row_index` bounds + index), and
    `_rebuild` (iterate visible; `max_row` from visible length).
  - **Keep whole-set** (full counts / status / column math, never
    cursor-indexed): `row_count`, `row_slugs`, `action_toggle_column` (the
    "All/None" toggle stays whole-column — see Approach §2), and the App's
    `_refresh_status_bar` rollup over `grid._rows` (status reflects the whole
    library, not the filtered view).
- Textual `Input` swallows some keys; the Down/Tab handler must `stop()` the
  event to prevent default behaviour. Tests 5–6 are the guard.
