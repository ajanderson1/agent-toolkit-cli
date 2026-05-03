# Plan — TUI: linked cells render blank because Rich parses `[x]` as markup

**Spec:** `docs/superpowers/specs/2026-05-03-tui-linked-cells-render-blank-design.md`
**Issue:** #2

## Scope

Single-character escape on the `linked` glyph + a regression test pinning the rendered output for both `linked` and `unlinked` states. Total churn ≈ 2 files, ~50 lines added.

## Tasks

### T1 — Apply the escape

**File:** `src/agent_toolkit_tui/widgets/asset_grid.py`

Change `_GLYPH["linked"]` from `"[x]"` to `r"\[x]"`.

The other three glyphs (`unlinked`, `unsupported`, `broken`) are unaffected — none have a leading `[` in a position Rich parses as markup. Pending overlays `+x ` and `-  ` (defined elsewhere in the file) are also unaffected for the same reason.

Acceptance: `git diff` shows exactly one substantive line changed in `_GLYPH`.

### T2 — Regression test

**File:** `tests/test_tui/test_asset_grid_glyphs.py` (new)

A focused test that:

1. Builds an `InventoryState` with at least two cells: one `linked`, one `unlinked`. (Use the same fixture pattern already used in `tests/test_tui/test_app.py` / `test_state.py`.)
2. Mounts an `AssetGrid` against that state in a Textual `App.run_test()` harness (already used in `test_headless.py` / `test_app.py`).
3. Asserts the `DataTable` cell at the `linked` row+col renders as `[x]` after Rich's markup pass — i.e. read back the rendered cell value, not the source string. The exact API: `table.get_cell_at(Coordinate(row, col))` returns the source string, but the test must check what Rich would *render*, not the stored value. Two approaches; pick whichever fits the existing test style:
    - **a.** Render the stored cell string through `rich.console.Console(file=io.StringIO(), force_terminal=False).print(cell, end="")` and assert the captured output contains `[x]` (and for `unlinked`, `[ ]`).
    - **b.** Use `Text.from_markup(cell).plain` and assert it equals `[x]` / `[ ]`. Lighter, no Console plumbing.

Prefer **(b)** unless `Text.from_markup` doesn't see the same parser path Textual uses (it does — Textual's DataTable applies markup via Rich's Text constructor).

Acceptance: test runs green; mutating `_GLYPH["linked"]` back to `"[x]"` makes the test fail.

### T3 — Quick local sanity

After T1+T2:

```bash
uv run pytest tests/test_tui/ -q
uv run pytest -q
```

Both pass. No other code changes implied.

## Out of scope (per spec)

- `rich.Text(...)` refactor of cell content.
- Visual/colour changes.
- Touching pending-glyph overlays (`+x `, `-  `).
- Investigating the `test_ingest_finalize.py` worktree contamination — separate issue.

## Risk

Vanishingly small. Single-char string change in a glyph constant; the rest of the rendering path is unchanged. The regression test pins the behaviour going forward, so the only realistic regression vector (someone reverts the escape without thinking) is caught.
