# Plan — #232 universal uninstall from project-scope TUI

## Task 1 — Tests first (TDD, red)
**File:** `tests/test_tui/test_skill_grid_apply.py`
- `test_toggle_universal_project_linked_queues_unlink`: build a `SkillRow` with
  `scope="project"` cells; `("universal","project")` linked. Mount in pilot app,
  `set_scope("project")`, cursor to the universal cell, press space, assert
  `pending_entries() == {("project","universal",slug): "unlink"}`.
- `test_toggle_universal_project_unlinked_queues_link`: same, `linked=False` → `"link"`.

**File:** `tests/test_cli/test_skill_install_engine.py`
- `test_apply_project_universal_unlink_removes_symlink`: install universal at project
  scope (mirror `test_apply_project_codex_gets_symlink_universal`), then
  `apply(InstallPlan(slug, scope="project", remove_agents=("universal",)))`, assert the
  `.agents/skills/<slug>` symlink is gone and the external-store canonical still exists.

Run → confirm the two grid tests fail (guard blocks the unlink) and clarify the engine
test passes already (proves the engine layer is done; it's a regression guard).

## Task 2 — Remove the guard (green)
**File:** `src/agent_toolkit_tui/widgets/skill_grid.py`
- Delete lines ~398-405: the comment block + the
  `if agent == "universal" and self._scope == "project" and cell.linked: return`.
- Leave the rest of `_toggle_at` intact.

## Task 3 — Verify
- `uv run pytest tests/test_tui/test_skill_grid_apply.py tests/test_cli/test_skill_install_engine.py`
- Full suite + lint pre-flight (flow Step 8).

## Risks
- `_row()` helper defaults `scope="global"` — pass `scope="project"` and construct the
  project cell explicitly; call `grid.set_scope("project")` after mount.
- `ensure_project_canonical` runs in app's apply path even for pure-remove; it's
  idempotent (returns early if canonical exists) — not exercised by the grid unit test,
  which stops at `pending_entries()`.
