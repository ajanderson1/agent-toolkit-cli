# Plan — Add the `instruction` kind to the TUI (#319)

Spec: `docs/superpowers/specs/2026-06-07-instruction-kind-tui-design.md`

TDD throughout: write the failing test for each unit, then the implementation.
New files mirror the agent kind (closest template). No edits to skill/pi/agent
behavior.

## Task 1 — `instruction_state.py` (data model)

New file `src/agent_toolkit_tui/instruction_state.py`, mirroring
`agent_state.py`.

- `Scope = Literal["global", "project"]`
- `INTERACTIVE_HARNESSES: tuple[str, ...] = ("claude-code", "gemini-cli")`
  (the two interactive symlink columns; `general` is rendered separately as a
  read-only column by the grid, not listed here).
- `@dataclass(frozen=True) InstructionCell: linked: bool; conflict: bool`
- `@dataclass InstructionRow: slug: str; source: str; canonical_exists: bool;
  cells: dict[tuple[str, str], InstructionCell]`  (key `(harness, scope)`)
- `_cell_for(slug, harness, *, scope, home, project) -> InstructionCell | None`
  — uses `instructions_adapters.symlink._pointer_path` to resolve the slot;
  `None` on `ValueError` (scope mismatch). `linked` = symlink resolves to
  canonical; `conflict` = slot exists but is a real file or foreign symlink.
- `build_instruction_rows(*, scope, home, project) -> list[InstructionRow]`:
  read the scope lock via `instructions_paths.lock_file_path` +
  `instructions_lock.read_lock`; resolve canonical via
  `instructions_paths.{global,project}_canonical_agents_md`; one row per slug
  (today: at most one, `AGENTS.md`). If the lock is empty but the canonical
  AGENTS.md exists, still emit a single `AGENTS.md` row so the user can install
  pointers from a fresh state. `canonical_exists` set from the resolved path.

**Test first:** `tests/test_tui/test_instruction_state.py`
- empty lock + no canonical → no rows (or a single row with
  `canonical_exists=False`, per the rule above — assert the chosen behavior).
- lock with `claude-code` listed + pointer symlinked → `linked=True`.
- pointer is a real file → `conflict=True`, `linked=False`.
- canonical present → `canonical_exists=True`.
- scope mismatch path (`replit` global, tested directly via `_cell_for`) → None.

## Task 2 — `widgets/instruction_grid.py` (the grid)

New file mirroring `widgets/agent_grid.py`. Class `InstructionGrid(Vertical)`.

- Same `PendingChanged` message; same `Op = Literal["link", "unlink"]`; same
  `_pending: dict[tuple[str, str, str], Op]` keyed `(scope, harness, slug)`.
- `id="instruction-table"` DataTable.
- **Columns** (in `_rebuild`): `INSTRUCTION ⓘ` (width 22), `general ⓘ`
  (read-only status, width 12), then one column per `INTERACTIVE_HARNESSES`
  (CLAUDE.md/GEMINI.md display names, width 14), then `Source` (width 30).
- Column index helpers account for the extra non-interactive `general` column
  at index 1: interactive harness columns start at index 2. `_harness_for_column`
  returns `None` for cols 0 (slug), 1 (general), and the source col.
- `_cell_glyph`: pending `+`/`-`; else `linked` → ✔, `conflict` → `[red]![/]`,
  missing → ☐, `None` → `[dim]—[/]`.
- `general` cell glyph: `✔` if `row.canonical_exists` else `[red]✘[/]`
  (non-toggleable; toggling it is a no-op).
- `action_toggle_cell` / `_toggle_at`: no-op on slug/general/source columns and
  on `conflict` cells (do not queue a toggle that the adapter will refuse —
  surface via `action_info` instead). Otherwise queue link/unlink like agent.
- `action_toggle_column` (`a`): same all/none logic, harness columns only.
- `action_info` (`i`): slug col → instruction summary (canonical path, scope);
  `general` col → explain it's the canonical AGENTS.md, native readers, and the
  install precondition; harness col → installed / not-installed / pending /
  conflict messaging + the equivalent `agent-toolkit-cli instructions install`
  CLI hint. Reuse `screens/cell_info.CellInfoScreen`.
- **Never** name any method `_render_*` (Textual flag collision — documented in
  agent_grid.py).

**Test first:** widget tests in `tests/test_tui/test_instruction_grid.py`
(columns render incl. general; row count; toggle link/unlink; toggle twice
clears; PendingChanged count; toggle_column; conflict cell non-toggle; general
cell non-toggle; set_scope clears pending).

## Task 3 — wire into `widgets/__init__.py`

Add `InstructionGrid` import + `__all__` entry.

## Task 4 — wire into `app.py`

Edits mirroring every place the agent kind is handled:

1. `Kind` literal → add `"instruction"`; `_KIND_LABELS` → add
   `"instruction": "Instruction"`.
2. Imports: `build_instruction_rows`, `InstructionGrid`.
3. `compose`: OptionList — add `Option("instruction", id="kind-instruction")`
   **first**, then a non-selectable separator option, then the existing three.
   Mount `InstructionGrid([], id="instruction-grid")` in the content Vertical
   (before the others is fine; visibility is display-toggled).
4. `_show_kind`: handle `"instruction"` (show instruction-grid, hide others,
   scope-toggle visible).
5. `on_option_list_option_selected`: map `kind-instruction` →
   `action_kind("instruction")`; ignore the separator option id.
6. `action_kind`: accept `"instruction"`; route refresh to
   `_refresh_instruction_view`.
7. `_refresh_instruction_view`: scope→roots, `set_scope`, `set_rows(
   build_instruction_rows(...))`.
8. `on_instruction_grid_pending_changed`: refresh footer + status.
9. `action_quit`: include instruction grid pending count.
10. `action_scope`: refresh instruction view when active.
11. `action_info_pass`, `action_refresh`, `action_revert`, `action_diff`:
    add the instruction branch.
12. `action_apply` → `_apply_instruction_pending` (Task 5).
13. `_build_content_header`, `_refresh_pending_label`, `_refresh_status_bar`:
    include instruction grid (status: `linked` / `pending`, like agent).

**Separator:** Textual `OptionList` supports `Separator` (`from
textual.widgets.option_list import Separator`) — use it for the divider. If a
plain visual nul option is cleaner, a disabled dim `Option` works too; prefer
`Separator` (idiomatic) and guard `on_option_list_option_selected` against a
`None`/separator option.

## Task 5 — `_apply_instruction_pending` in `app.py`

Per spec apply semantics:
1. `grid.pending_entries()`; group by `(scope, slug)` → (adds, removes) of
   harnesses.
2. For each `(scope, slug)`: resolve `home`/`project`; read lock via
   `instructions_paths.lock_file_path` + `instructions_lock.read_lock`; mutate
   the slug entry's `harnesses` (create entry with `source="AGENTS.md"` if
   absent and there are adds); `write_lock`.
3. `instructions_install.apply(scope=scope, project_root=project, home=home)`;
   count created/removed from the returned `Plan.actions`.
4. `CanonicalMissingError` / `PointerConflictError` → append to errors, footer
   `[red]apply failed[/]` + `notify`, exactly like `_apply_agent_pending`.
5. On full success clear pending; else `restore_pending`; refresh view +
   labels + status.

**Test first (app-level):** in `test_instruction_grid.py`, mirror
`test_agent_grid.py` app-level tests: sidebar lists instruction first +
separator; switching shows InstructionGrid hides others; `ctrl+s` routes to
`_apply_instruction_pending`; apply link writes lock + drives
`instructions_install.apply` (assert pointer created on disk); apply unlink
removes pointer; canonical-missing surfaces notify+footer; conflict slot is not
clobbered (real file still present after a no-op apply).

## Task 6 — CSS

`css/app.tcss`: add `InstructionGrid { height: 1fr; }` +
`InstructionGrid DataTable { height: 1fr; }` (mirrors AgentGrid block). Style
the separator dim if needed.

## Task 7 — full verification

- `ruff check`, `ruff format --check`, `mypy --strict src/agent_toolkit_tui`
  (match repo config).
- `pytest tests/test_tui` green (existing + new).
- Launch TUI manually (`run.log`) to confirm rendering.

## Risks / notes

- **`_render_*` collision** — already documented; do not name glyph helpers
  `_render_*`.
- **Empty-lock first-run** — decide & test the "canonical exists but lock empty"
  row behavior so a fresh user can install pointers from the grid.
- **Apply reconciles whole lock** — the lock-mutation-then-`apply` ordering is
  the crux; the install facade prunes, so writing the lock first is what makes
  add/remove correct.
- **Conflict cells** — must be visibly non-clobbering; this is a graded DoD item.
