# Plan — align all `list` command output into padded tables (#336)

Spec: `docs/superpowers/specs/2026-06-08-align-list-command-output-design.md`

TDD throughout: write the failing test first, then make it pass.

## Task 1 — `table.py` helper (RED → GREEN)

1. Write `tests/test_cli/test_table.py`:
   - `test_aligns_mixed_width_columns`: rows with short + long first cells → in the rendered output, every row's second column starts at the same character offset.
   - `test_double_width_glyphs_do_not_break_alignment`: a column whose cells are `✔` / `☐` (width-2) mixed with multi-char strings → the following column still aligns by **display** width, not `len()`.
   - `test_header_row_widens_columns`: a header longer than any cell forces the column wider; cells align under the header.
   - `test_no_trailing_whitespace`: last column is not right-padded; no line ends in a space.
   - `test_empty_rows_returns_empty_string`.
2. Implement `src/agent_toolkit_cli/table.py`:
   - `def display_width(s: str) -> int` — sum `2` for `unicodedata.east_asian_width(c) in ("W", "F")`, else `1`.
   - `def render_table(rows, headers=None) -> str` — compute per-column max display width (incl. header), left-pad each cell to `col_width - display_width(cell)` trailing spaces, join columns with `"  "`, strip trailing space on the last column, `\n`-join. Empty `rows` and no headers → `""`.
3. Run `uv run pytest tests/test_cli/test_table.py -q` → green.

## Task 2 — refactor `instructions list` onto the helper (keep it green)

1. `instructions list` already has matrix tests (`tests/test_cli/test_instructions_matrix.py`). Confirm they assert on content, then refactor `list_cmd.py`:
   - Build `rows = [[r["harness"], r["verdict"], r["default_file"]] for r in rows]`.
   - `click.echo(render_table(rows, headers=["HARNESS", "VERDICT", "DEFAULT FILE"]))`.
   - Delete the hand-rolled `width = max(...)` / `:<{width}` block.
2. If existing tests pin exact spacing (e.g. `VERDICT` padded to 15), update them to assert alignment/content rather than the old hardcoded widths — the helper's widths are data-driven, which is the point. Prefer asserting "columns align" + "expected cells present" over brittle exact-string matches.
3. `uv run pytest tests/test_cli/test_instructions_matrix.py -q` → green.

## Task 3 — route `pi-extension list` (RED → GREEN)

1. Add `tests/test_cli/test_pi_extension_list_table.py`: invoke the command (CliRunner) over a fabricated inventory with mixed-width slugs + glyph cells; assert columns align and no raw `\t` in output.
2. Edit `pi_extension/list_cmd.py`: replace the per-row `click.echo(f"...\t...")` loop with one `rows = [[r.slug, g, p, r.origin, r.source] for r in records]` + `click.echo(render_table(rows))`. Leave `--json` and the empty-state message untouched.
3. Green.

## Task 4 — route `skill list` (RED → GREEN)

1. Add a table-alignment test for `skill list` (CliRunner over a fabricated lock with mixed-width slugs).
2. Edit `skill/list_cmd.py` `_emit_table`: build `rows = [[slug, e.source, e.ref or "(default)", (e.upstream_sha or "")[:7]] for slug in slugs]` + `click.echo(render_table(rows))`. Keep both empty-state branches and `_emit_json` untouched.
3. Green.

## Task 5 — route `agent list` (RED → GREEN)

1. Add a table-alignment test for `agent list` (CliRunner over a fabricated lock; marker column + mixed-width slugs).
2. Edit `agent/list_cmd.py`: build `rows = [[marker, slug, f"{entry.source}{ref_display}", f"[{n} harnesses]"] for ...]` + `click.echo(render_table(rows))`. Keep `--json` and `no agents found` untouched.
3. Green.

## Task 6 — full suite + manual smoke

1. `uv run pytest -q` → all green.
2. `uv run ruff check src tests` (or the project lint) → clean.
3. Manual: `uv run agent-toolkit-cli pi-extension list` / `skill list -g` / `agent list -g` / `instructions list` — eyeball that columns line up. Capture to `assets/verification/336/`.

## Notes / risks

- The only real subtlety is the glyph width; `unicodedata.east_asian_width` is stdlib and reliable for the two glyphs in use. Do not add `wcwidth` as a dependency — out of scope.
- `agent list`'s current marker is `f"{marker}  {slug}"` (marker glued to slug with 2 spaces). Splitting marker into its own column preserves the same visual (gutter is also 2 spaces) while making it align as a real column.
- Keep changes surgical: do not touch `--json` serialisation, empty-state strings, or column ordering.
