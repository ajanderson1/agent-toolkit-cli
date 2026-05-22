# Design: TUI info-panel cosmetics (#212)

## Goal

Four small TUI cosmetic fixes on the Skills tab info surfaces. All four are
presentation-layer adjustments — no change to skill resolution, scope detection,
or lockfile shape.

## Scope (the four fixes)

### 1. Project-scope info panel shows skill description

**Today**: `SkillRow.description` is populated by `_read_skill_description(canonical)`
where `canonical = canonical_skill_dir(slug, scope=scope, ...)`. At project scope,
if the project canonical does not yet exist (`state == "library"`), the function
short-circuits to `""` because the project canonical dir is absent. The slug-cell
info modal then renders no `Description:` block.

**Fix**: when the project canonical is missing/empty, fall back to reading the
description from the **library canonical** (`library_skill_path(slug)`). Source
of truth for description is the library copy anyway; project scope just inherits.

**Location**: `src/agent_toolkit_tui/skill_state.py`, `build_skill_rows()` (lines
~145–199). Change the `description=_read_skill_description(canonical)` line so
the fallback path tries `library_skill_path(slug)` when the project-scope read
returns empty. Helper: a tiny wrapper or an extra arg keeps `_read_skill_description`
unchanged.

### 2. Global-install marker text gated on actual global presence

**Today**: `column_info._universal_info()` always appends the `🌐 marker (project
scope only): "This skill is also installed globally, so you may not need it at
project scope too."` block to the Universal column info text. Because column-info
is rendered without per-cell context, the explanation shows even for skills that
are NOT installed globally — exactly the user complaint.

**Fix**: make the column-info contract context-aware. Two viable options:

| Option | Sketch | Verdict |
|---|---|---|
| A. Make factories take an optional context dict (`scope`, `slug`, `cells`). Universal factory only includes the 🌐 paragraph when the focused row's global cell is linked. | Touches `get_column_info()` signature + every caller. | Chosen |
| B. Keep factory signature; pre-compute "should show marker" elsewhere; conditional renders inside the modal. | Splits the policy across two files. | Rejected |

Going with A — call sites already know the focused row. Signature change:
`get_column_info(name, *, context=None) -> ColumnInfo | None` where `context`
is a `dict[str, object]` carrying `{ "scope", "slug", "global_linked" }` for the
Universal case. Existing keys without context just ignore it.

The block is omitted when `context["global_linked"] is False`. It still shows
when context is absent (no caller info) and when the cell is globally linked.

**Location**:
- `src/agent_toolkit_tui/column_info.py` — change `_universal_info` to accept
  context, adjust `COLUMN_INFO` value types, and update `get_column_info()`.
- `src/agent_toolkit_tui/widgets/skill_grid.py` — `action_open_column_info()`
  builds the context (current scope, focused row's slug, whether its global
  universal cell is linked) before invoking `get_column_info()`.

### 3. `ⓘ` glyph on every column that has an info panel

**Today**: `SkillGrid._rebuild()` only appends `ⓘ` for columns whose key is in
`COLUMN_INFO` (i.e. `universal`, `state`). But agent columns (Claude Code, Pi)
expose per-cell info via `CellInfoScreen`, and the slug column does too. The
Source column is documented as passive — no panel — so no glyph.

**Fix**: glyph the slug column (always — `i` on a slug cell opens slug info),
glyph the agent columns Claude Code and Pi (`i` on a cell opens `CellInfoScreen`),
keep glyph on `State`, and keep `Source` ungly­phed. In other words: every column
except `Source` gets the glyph.

Per `_rebuild`, this is one tweak per `table.add_column(...)` call.

**Location**: `src/agent_toolkit_tui/widgets/skill_grid.py`, `_rebuild()` (lines
~404–417).

### 4. `library` state placeholder displays as `—`

**Today**: the slug-cell info modal builds the body with `f"State:  {row.state}"`.
For the `library` state that prints the literal word "library" which reads as
broken UI rather than "not-installed-yet, no meaningful state".

**Fix**: at the display layer (not the data model), translate `state == "library"`
to `"—"` (em dash) when building the modal body. Keep `row.state` as-is for the
internal model and for the grid's per-row `State` column (which already renders
it dimmed via `_STATE_MARKUP["library"]`).

**Location**: `src/agent_toolkit_tui/widgets/skill_grid.py`, `action_info()`
(line ~175) — single string substitution at the body-build site.

## Out of scope

- Refactoring `column_info.py` away from factories.
- Changing how the grid resolves columns by index, or refactoring the column layout.
- Changing the `library` state semantic — only its display in the slug-cell modal.
- The wider Skills grid layout / column set.

## Tests

Each fix gets at least one new assertion:

1. **Description fallback**: extend `tests/test_tui/test_skill_state.py` —
   project scope, slug in library lock, project canonical absent (state="library")
   → `SkillRow.description` is the library canonical's description, not `""`.
2. **Marker gating**: in `tests/test_tui/test_column_info.py` —
   `_universal_info(context={"global_linked": False})` produces output with no 🌐
   paragraph; `context={"global_linked": True}` keeps it. Plus: context-less call
   stays back-compat (keeps the paragraph).
3. **Glyph coverage**: in `tests/test_tui/test_skill_grid_column_info.py` or
   `_new_columns` — after `_rebuild`, every column label except `Source` contains
   `ⓘ`. (Read labels off the DataTable.)
4. **State placeholder**: in `tests/test_tui/test_cell_info.py` or a new test —
   slug-cell info modal for a `library`-state row contains `State:  —` and not
   `State:  library`.

All four are behavioural, not snapshot.

## Notes

- `description` field on SkillRow stays a single string. The fallback merely
  changes where it's read from when the project canonical is empty.
- `get_column_info()` signature change is localised — only the TUI module uses it.
- The em dash `—` matches the convention noted in the issue's DoD ("our
  convention for 'no meaningful state'"). Used as a literal character, not a
  constant — no need for a new helper.
