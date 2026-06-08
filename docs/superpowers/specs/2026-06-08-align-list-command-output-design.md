# Design — align all `list` command output into padded tables

Issue: #336 · Type: fix · Milestone: v4.0.0

## Problem

Three of the four CLI `list` commands print raw tab-separated rows:

- `pi-extension list` → `f"{r.slug}\t{g}\t{p}\t{r.origin}\t{r.source}"`
- `skill list` → `f"{slug}\t{e.source}\t{ref}\t{short}"`
- `agent list` → `f"{marker}  {slug}\t{entry.source}{ref_display}\t[{n} harnesses]"`

Tabs do not align when cell widths vary, and the `✔`/`☐` status glyphs are East-Asian-Width "Wide" (display width 2, `len()` 1), so even a naive `:<width`-pad on `len()` would still drift by one column per glyph cell. The result is the ragged output in the issue screenshot.

Only `instructions list` already pads — it computes `max(len(...))` and left-justifies. It is the convergence target, but its padding is also `len()`-based (it has no glyph columns so it has never been bitten).

## Goal

Every `list` command emits a clean, column-aligned, human-readable table. Columns left-align and pad to a consistent per-column **display** width so rows line up vertically regardless of cell content — including the double-width glyph cells.

## Approach (chosen in #336: shared table helper)

New module `src/agent_toolkit_cli/table.py` exposing one function:

```python
def render_table(rows: list[list[str]], headers: list[str] | None = None) -> str
```

- **Display-width aware.** Per-cell width uses a `display_width(s)` helper that sums `2` for East-Asian "Wide"/"Fullwidth" code points (covers `✔` U+2714 and `☐` U+2610 as rendered in a typical terminal — both are width-2 in practice) and `1` otherwise. This is the only way `len()`-padding's off-by-one on glyph columns gets fixed.
- **Per-column width** = max display width across that column's cells (and the header, if given).
- **Left-pad** every cell to its column width by appending spaces (pad count = `col_width - display_width(cell)`), so alignment survives wide glyphs.
- **Gutter** = two spaces between columns (matches `instructions list`'s existing `  ` gutter).
- Last column is **not** right-padded (no trailing whitespace).
- Returns a single `\n`-joined string (no trailing newline); callers `click.echo` it. Empty `rows` → empty string.
- No colour, no borders, no Rich. Pure stdlib. New runtime dependency is explicitly out of scope.

The double-width detection uses `unicodedata.east_asian_width` (stdlib) — `"W"` and `"F"` → width 2. The two glyphs in use both report wide; the helper is general so future glyph columns inherit correct handling.

## Wiring

All four `list_cmd.py` build a `list[list[str]]` of string cells and `click.echo(render_table(rows))`:

- **pi-extension list** — columns: slug, global(✔/☐), project(✔/☐), origin, source. No header (current output has none).
- **skill list** — columns: slug, source, ref, short-sha. No header (current output has none).
- **agent list** — the leading marker becomes its own first column; columns: marker(✔/☐), slug, source(+ref), `[N harnesses]`. No header.
- **instructions list** — refactor onto `render_table` with `headers=["HARNESS", "VERDICT", "DEFAULT FILE"]` (it is the only one with a header today; preserve it). Drop its hand-rolled `:<{width}` block.

Empty-state messages (`"no pi extensions found"`, `"(no skills installed)"`, `"no agents found"`, etc.) and **all `--json` paths stay exactly as they are** — the helper is only for the human table body.

## Out of scope

- `--json` output (machine-readable, untouched).
- TUI grids in `agent_toolkit_tui/` — CLI `list` verbs only.
- Colour / Rich / borders / box-drawing — plain padded text only, no new dependency.
- Re-ordering or renaming existing columns — same columns, just aligned.

## Definition of done

- `src/agent_toolkit_cli/table.py` with `render_table` + a private `display_width` helper, double-width-glyph aware.
- `pi-extension list`, `skill list`, `agent list` route human output through it — no raw `\t` left in any human echo.
- `instructions list` refactored onto the same helper, header preserved.
- Existing columns and every `--json` behaviour unchanged.
- A unit test asserts column alignment for a mixed-width row set (short + long slugs, glyph cells): every rendered row, when split at column starts, has its second-column character at the same offset.
