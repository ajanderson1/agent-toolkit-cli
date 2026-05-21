# Plan: TUI SkillGrid — description + upstream-source columns

**Spec:** `docs/superpowers/specs/2026-05-22-tui-skillgrid-desc-source-cols-design.md`
**Issue:** #182
**Mode:** `--ship-it`

Linear, single-agent plan. No parallel tasks — every change touches the same two files (`skill_state.py`, `widgets/skill_grid.py`) plus their tests.

## Task 1 — extend SkillRow + frontmatter read

**Files:** `src/agent_toolkit_tui/skill_state.py`

1. Add `description: str = ""` to `@dataclass class SkillRow`. Default empty so existing test constructors keep working.
2. Add module-private helper `_read_skill_description(canonical: Path) -> str`:
   - If `canonical` doesn't exist or is not a directory → `""`.
   - Read `canonical / "SKILL.md"`. On `OSError` → `""`.
   - If text doesn't start with `"---\n"` → `""`.
   - Find closing `"\n---"` (start search at offset 4) — if not found → `""`.
   - `yaml.safe_load(text[4:end])`. On `yaml.YAMLError` or non-dict → `""`.
   - Return `str(fm.get("description") or "").strip()`. Collapse newlines/tabs to spaces so the cell stays single-line.
3. In `build_skill_rows()`, after the existing per-row block that computes `state`, populate `description=_read_skill_description(canonical)` on the row construction.
4. Add `import yaml` at the top (already a project dep — used in `commands/skill/__init__.py`).

**Acceptance:**
- `pytest tests/test_tui/` still imports without error.
- `SkillRow(slug="x", source="y", ref="main", state="clean")` still constructs (default `description=""`).

## Task 2 — render new columns in SkillGrid

**Files:** `src/agent_toolkit_tui/widgets/skill_grid.py`

1. In `_rebuild(self, table)`:
   - After `table.add_column("slug", width=20)` → add `table.add_column("description", width=40)`.
   - Existing agent-column loop unchanged.
   - After `table.add_column("state", width=10)` → add `table.add_column("source", width=30)`.
   - In the per-row cell list, after `cells: list[str] = [row.slug]` → append `row.description`, then existing agent glyphs, then state markup, then `row.source`.
2. In `_column_index(self, agent_name)`: change `1 + list(INTERACTIVE_AGENTS).index(agent_name)` → `2 + list(INTERACTIVE_AGENTS).index(agent_name)` (slug=0, description=1, agents start at 2).
3. In `_agent_for_column(self, col)`:
   - `if col < 2: return None` (was `if col == 0`).
   - `idx = col - 2` (was `col - 1`).
   - Bounds check unchanged in form: `0 <= idx < len(INTERACTIVE_AGENTS)`.
4. In `_rebuild()` cursor restore: `max_col = 2 + len(INTERACTIVE_AGENTS) + 1` (description + agents + state + source — same as before plus 2 new columns). Actually simpler to compute as `table.column_count - 1` after all `add_column` calls; refactor if cleaner.
5. Update the module docstring (`Columns: slug | claude-code | pi | state.`) to `Columns: slug | description | universal | claude-code | pi | state | source.`

**Acceptance:**
- Running the TUI (verify step) renders the new columns.
- Cursor-on-`slug` and cursor-on-`description` and cursor-on-`state` and cursor-on-`source` all return `None` from `_agent_for_column` and so are silently ignored by `action_toggle_cell` / `action_toggle_column` / `action_open_column_info` — matching today's behaviour for `slug` and `state`.

## Task 3 — update existing tests for shifted coordinates

**Files:** `tests/test_tui/test_skill_grid_apply.py`, `tests/test_tui/test_skill_grid_column_info.py`, `tests/test_tui/test_column_info.py`, `tests/test_tui/test_column_info_modal.py`

1. Run `uv run pytest -q tests/test_tui/` once **before** edits to capture the failing-test list — that defines the working set.
2. For each failing assertion that references a hardcoded column index (`Coordinate(row, column)`, `cursor_coordinate.column == N`, etc.) referring to an agent column:
   - Shift the column index by **+1** (agent columns moved right by one because of the new `description` column at index 1).
3. For any assertion about the total column count, expected count is `1 + 1 + len(INTERACTIVE_AGENTS) + 1 + 1` (slug, description, agents, state, source) — today's is `1 + len(INTERACTIVE_AGENTS) + 1`.
4. Do **not** add new behavioural changes here — only re-baseline the coordinate math.

**Acceptance:**
- `uv run pytest -q tests/test_tui/` is green.

## Task 4 — new tests covering the new columns

**Files:** `tests/test_tui/test_skill_grid_new_columns.py` (new)

Three small unit tests:

1. **`test_description_column_position`** — build a `SkillGrid` with two `SkillRow`s, mount via the existing Textual app harness used by other TUI tests. Assert the second `DataTable` column label is `"description"` and the per-row cell text equals each row's `description` field.
2. **`test_source_column_is_last`** — same fixture. Assert the last column label is `"source"` and the per-row cell equals `row.source`.
3. **`test_description_empty_for_library_rows`** — construct a `SkillRow` with `state="library"` and `description=""`. Assert the description cell renders as `""` (i.e. the empty string, not `None`, not the string `"None"`).

Optionally a fourth:

4. **`test_read_skill_description_handles_missing_skillmd`** — unit test on `_read_skill_description` directly: passing a `tmp_path` directory with no `SKILL.md` returns `""`. Passing one with a `SKILL.md` containing `---\nname: foo\ndescription: hi there\n---` returns `"hi there"`. Passing one without frontmatter returns `""`.

**Acceptance:**
- All four tests pass.
- `uv run pytest -q` overall is green.

## Task 5 — verify locally

1. `uv run pytest -q` — full suite green.
2. `uv run agent-toolkit-tui --help` (or whichever TUI entry-point exists per `pyproject.toml`) — sanity check the binary still starts (no import errors from the model change).

## Sequencing

Tasks 1 → 2 → 3 → 4 → 5, in order. Each task ends with a single conventional commit so the diff narrates the change cleanly.
