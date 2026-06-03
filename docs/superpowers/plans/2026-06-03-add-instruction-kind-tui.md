# Plan — Add 'instruction' kind to TUI (#319)

Spec: `docs/superpowers/specs/2026-06-03-add-instruction-kind-tui-design.md`

TDD throughout: write the failing test first, then make it pass. Each task is an
independent, committable unit. Run `uv run pytest -q` after each.

---

## Task 1 — TUI state module: `instruction_state.py`

**New file:** `src/agent_toolkit_tui/instruction_state.py` (mirror `agent_state.py`).

- `INTERACTIVE_HARNESSES: tuple[str, ...] = ("claude-code", "gemini-cli")`.
- `@dataclass InstructionCell`: `applicable: bool`, `linked: bool`.
  - `applicable=False` when the harness has no slot for the scope
    (catch `ValueError` from `symlink._pointer_path`).
  - `linked=True` iff the pointer `is_symlink()` and `resolve() == canonical.resolve()`.
- `@dataclass InstructionRow`: `slug` (always `"AGENTS.md"` / the canonical source),
  `scope`, `general_linked: bool` (canonical AGENTS.md present for scope),
  `cells: dict[str, InstructionCell]` keyed by harness name.
- `build_instruction_rows(*, home: Path | None, project: Path | None) -> list[InstructionRow]`:
  - One row per scope that has a lock entry (read via
    `instructions_lock.read_lock(instructions_paths.lock_file_path(scope, project))`),
    OR build both scopes from the catalog if that's how agent_state does it —
    follow `agent_state.build_*` precedent.
  - `general_linked`: canonical `AGENTS.md` exists at the scope's canonical path
    (`instructions_paths.global_canonical_agents_md()` /
    `project_canonical_agents_md(project)`).
  - For each harness in `INTERACTIVE_HARNESSES`, probe `_pointer_path` (try/except
    `ValueError` → `applicable=False`).

**Test (write first):** `tests/test_tui/test_instruction_state.py`
- `INTERACTIVE_HARNESSES == ("claude-code", "gemini-cli")`.
- `build_instruction_rows` on a tmp project with `AGENTS.md` + a symlinked
  `CLAUDE.md` → row with `cells["claude-code"].linked is True`,
  `cells["gemini-cli"].linked is False`.
- `replit`-style not-applicable path returns `applicable=False` (if probed) — only
  if a non-applicable harness is in the column set; with claude-code+gemini-cli both
  are dual-scope, so cover not-applicable via a direct unit test of the probe helper.

**Reference:** `agent_state.py:_cell_for` (the `try/except ValueError` guard).

**Commit:** `feat(tui): instruction_state — rows + cells for instruction kind (#319)`

---

## Task 2 — `InstructionGrid` widget

**New file:** `src/agent_toolkit_tui/widgets/instruction_grid.py` (copy `agent_grid.py`,
adapt toward `pi_grid.py`'s two-scope-no-toggle shape).

- `class InstructionGrid(Vertical)`.
- Inner `DataTable` id `#instruction-table`.
- Columns in order: `INSTRUCTION ⓘ` (the `general` column showing canonical
  AGENTS.md state) · `Claude Code ⓘ` · `Gemini CLI ⓘ` · `Source`.
  - First data column = `general`; per the spec it's the canonical-install indicator.
- Rows: one per scope present (global / project), labelled by scope.
- `PendingChanged(Message)` inner class.
- `_pending: dict[tuple[str, str, str], str]` — key `(scope, harness, slug)`,
  value `"link"` | `"unlink"`.
- Space toggles the focused harness cell (not the `general`/`source` columns):
  computes desired op from current `linked` state, stores/clears pending,
  posts `PendingChanged`.
- `set_rows()`, `pending_entries()`, `clear_pending()`, `restore_pending()`,
  `_notify_pending()`, `_rebuild()`, `_cell_glyph()` — match agent_grid API.
- **No method named `_render_*`** (Textual collision).
- Not-applicable cells render a muted glyph (e.g. `·`) and are not toggleable.

**Wire export:** add `InstructionGrid` to `src/agent_toolkit_tui/widgets/__init__.py`.

**Test (write first):** `tests/test_tui/test_instruction_grid.py` — mirror
`test_agent_grid.py`:
- Columns include `INSTRUCTION`, `Claude Code`, `Gemini CLI`.
- Row count == number of scopes with entries.
- Space on a claude-code cell that is currently unlinked → pending
  `{("global","claude-code","AGENTS.md"): "link"}`.
- Space on a linked cell → `"unlink"`.
- Toggling back to original clears the pending entry.
- `PendingChanged` posted on toggle.

**Commit:** `feat(tui): InstructionGrid widget — general + claude-code + gemini-cli (#319)`

---

## Task 3 — CSS

**Edit:** `src/agent_toolkit_tui/css/app.tcss` — add an `InstructionGrid { ... }`
block mirroring the existing `AgentGrid` block (`height: 1fr;` etc.).

No separate test (covered by app composition test in Task 4).

**Commit:** folded into Task 4 commit (CSS-only, trivial).

---

## Task 4 — Wire into `app.py` (sidebar order + dispatch)

**Edit:** `src/agent_toolkit_tui/app.py`. Follow every existing dispatch site
(scout enumerated them):

1. Import `InstructionGrid` and `build_instruction_rows`.
2. `Kind = Literal["skill", "pi-extension", "agent", "instruction"]`.
3. `_KIND_LABELS["instruction"] = "Instruction"`.
4. `compose()`:
   - Add `Option("Instruction", id="kind-instruction")` to the `OptionList`
     **first** (above skill), then a visual **separator** (`OptionList.add_option(None)`
     / a `Separator`) between instruction and the rest.
   - Yield `InstructionGrid([], id="instruction-grid")` in the content area,
     `display=False` initially (skill stays default-active).
5. `_show_kind()` — set `instruction-grid` display in all branches + add the
   `"instruction"` branch.
6. `on_option_list_option_selected()` — `elif opt_id == "kind-instruction": self.action_kind("instruction")`.
7. `action_kind()` — extend the whitelist guard to include `"instruction"`;
   call `_refresh_instruction_view()`.
8. Add `_refresh_instruction_view()` — calls `build_instruction_rows(...)`,
   `grid.set_rows(...)`.
9. Add `_apply_instruction_pending()`:
   - For each pending `(scope, harness, slug) -> op`, call
     `instructions_install.apply(...)` / `instructions_install.uninstall(...)`
     for the scope.
   - **Catch `PointerConflictError` (and `InstallError`-family)** → `notify(...,
     severity="error")`, surface in footer "apply failed: …". Do **not** swallow.
   - On success, refresh view + footer "applied: N".
10. Add `on_instruction_grid_pending_changed()` handler.
11. Include `instruction-grid` pending counts in `action_quit()`, `action_revert()`,
    `action_diff()`, `action_apply()`, `_refresh_pending_label()`,
    `_refresh_status_bar()` (add explicit `elif active == "instruction"` so the
    `else` agent-catch-all doesn't misfire), `action_info_pass()`.

**Tests (write first):** `tests/test_tui/test_app_instruction.py`
- Sidebar `OptionList` prompts include `"Instruction"` and it appears **before**
  `"Skill"` (assert index order). Confirms "above other kinds" + separator present.
- Selecting the instruction option shows `#instruction-grid` and hides others.
- Existing kinds still render (skill/pi/agent grids present) — regression guard.
- Apply routing: monkeypatch `instructions_install.apply` → assert called with the
  pending scope; footer shows "applied:".
- `PointerConflictError` path: monkeypatch `apply` to raise → footer shows error,
  `notify` severity error (mirror agent_grid's apply-failure test).

**Update existing tests** that assert "three kinds": the scout flagged
`test_kind_sidebar_lists_three_kinds` (and any sibling). Update to expect
`instruction` in the prompt set and the new ordering. Do **not** weaken assertions
beyond what the change requires.

**Commit:** `feat(tui): render instruction kind above other kinds with separator (#319)`

---

## Task 5 — Efficacy + no-clobber tests (DoD-critical)

**New file:** `tests/test_tui/test_instruction_efficacy.py` (or co-locate in the CLI
e2e test dir if that's the better home — follow `test_instructions_install_e2e.py`).

- **Create:** build a tmp project with canonical `AGENTS.md`, run the apply path
  (via the TUI `_apply_instruction_pending` or directly through
  `instructions_install.apply`) for `claude-code` → assert
  `(project/"CLAUDE.md").is_symlink()` and `.resolve() == (project/"AGENTS.md").resolve()`.
- **Remove:** then uninstall → assert pointer no longer a symlink / absent, and the
  canonical `AGENTS.md` is untouched.
- **No-clobber:** place a **real** `CLAUDE.md` file at the target, attempt apply →
  assert `PointerConflictError` raised and the real file content is unchanged.

This directly discharges the DoD's "efficacy checks confirm symlinks are
created/removed" and "does not clobber non-symlink files".

**Commit:** `test(tui): instruction symlink efficacy + no-clobber (#319)`

---

## Verification (flow Step 9)

No `.claude/testing.md`, no `verify.sh`. Legacy menu → **terminal** recipe: the
package ships a TUI; capture `uv run agent-toolkit-tui --help` (or the documented
entry) to `run.log`. The substantive proof of behaviour is the pytest suite
(efficacy + grid render tests) which Step 8 pre-flight already runs.

## Risks (from scout)

- `replit` is project-only — not in the chosen column set, but the probe helper must
  still guard `ValueError`.
- `augment`+`claude-code` share `CLAUDE.md` at project scope — a single pointer can
  make both read as linked; that's correct by the model. Our columns only show
  `claude-code`, so no display conflict.
- Don't change the default active kind (keep `skill`) — avoids churning unrelated tests.
- Surface `PointerConflictError`; never swallow.
