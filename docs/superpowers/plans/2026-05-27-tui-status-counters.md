# Plan — Fix TUI status counters (#250)

TDD: write/extend tests first where practical, then implement, then verify.

## Task 1 — Live Pending count (Bug 1)

**Files:** `src/agent_toolkit_tui/widgets/skill_grid.py`, `src/agent_toolkit_tui/app.py`

1. Add a `PendingChanged(Message)` nested message class to `SkillGrid` carrying
   `count: int`.
2. Add a private `_notify_pending()` helper that posts
   `self.PendingChanged(len(self._pending))`.
3. Call `_notify_pending()` after every `_pending` mutation:
   `_toggle_at`, `action_toggle_column`, `clear_pending`, `restore_pending`,
   `set_rows`, `set_scope`.
4. In `TUIApp`, add `on_skill_grid_pending_changed(self, event)` that calls
   `_refresh_pending_label()` and `_refresh_status_bar()`.

**Tests** (`tests/test_tui/`):
- New: toggling a cell drives the footer `#footer-pending` to `Pending: 1`;
  toggling back returns it to `Pending: 0`. Use the full `TUIApp` (or a minimal
  host app that reproduces the message wiring) via `run_test()`/pilot.
- Guard naming: no `_render_*` method introduced.

## Task 2 — Per-harness applied count (Bug 2)

**File:** `src/agent_toolkit_tui/app.py` (`_apply_skill_pending`)

1. Capture `result = engine_apply(...)`; on success add
   `len(result.created) + len(result.removed)` to `ok`.
2. On `InstallError` (engine_apply or ensure_project_canonical), add
   `len(adds) + len(removes)` (intended writes for the group) to `failed`.
3. Leave the footer/notify summary strings unchanged in shape
   (`applied: {ok} ok, {failed} failed`).

**Tests** (`tests/test_tui/`):
- New unit-ish test that drives `_apply_skill_pending` with a monkeypatched
  `engine_apply` returning an `InstallResult` with 3 `created` paths for a
  single-slug, 3-agent pending set → footer reads `applied: 3 ok, 0 failed`.
- Failure path: monkeypatched `engine_apply` raising `InstallError` for a
  3-agent group → `failed` reflects 3 (symmetric).

## Task 3 — Verify + regression

- `uv run pytest -q` green (full suite — pre-flight CI).
- Manual TUI smoke captured as a verification artifact (terminal `--help` /
  pilot-driven counter assertions logged).

## Risks / notes

- Textual message names: handler is `on_skill_grid_pending_changed`; avoid
  `_render_*` (collides with internal flags → 'bool not callable').
- `set_scope`/`set_rows` clear `_pending`; posting after them keeps the footer
  consistent when scope flips. Posting a message before the widget is mounted is
  a no-op-safe in Textual (messages queue), but guard if needed.
