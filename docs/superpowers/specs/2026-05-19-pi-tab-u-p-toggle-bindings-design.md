---
issue: 107
title: TUI Pi tab — u/p toggle bindings (load/unload from the tab)
date: 2026-05-19
status: drafted
---

# TUI Pi tab — u/p toggle bindings

## 1. Context

PR #106 shipped the read-only Pi tab. The original Pi unified-inventory spec
(`2026-05-19-pi-unified-extension-inventory-design.md` §4.5) called for `u`/`p`
toggle bindings that route through the existing CLI verbs (`pi load`, `pi
unload`). That hook was explicitly deferred at the end of PR #106 to keep the
first cut shippable; the deferred-binding note in
`src/agent_toolkit_tui/widgets/pi_tab.py:8-12` is the breadcrumb.

This spec closes that gap. No scope creep — same verbs, same modal, same
inventory; just bindings + a runner shell-out + refresh.

## 2. Goal

From the Pi tab modal, the operator can:

- Highlight a row.
- Press `u` to toggle user-scope load state for that extension.
- Press `p` to toggle project-scope load state for that extension.
- See the table refresh with the new state immediately after.
- See a one-line error in the modal footer if the toggle failed (no crash).

## 3. Acceptance

1. `u` on a row where `user_loaded=false` runs `pi load --scope user <slug>`,
   then re-renders the table; the row's `U` column flips to `✓`.
2. `u` on a row where `user_loaded=true` runs `pi unload --scope user <slug>`,
   then re-renders; the `U` column flips back to blank.
3. `p` mirrors (2) and (3) for the `P` column / project scope.
4. A non-zero CLI exit surfaces in the modal footer as a single line
   (`pi load error: <stderr first line>`); the modal stays open and the table
   keeps its prior state.
5. Bindings are screen-scoped (on `PiTabScreen`), not app-global; pressing
   `u`/`p` outside the modal does nothing new.
6. At least one Pilot-driven test exercises the happy path (press `u` →
   runner method called with right args → table reflects new state).

## 4. Design

### 4.1 Runner

Add to `src/agent_toolkit_tui/runner.py` (mirroring `pi_inventory`):

```python
def pi_load(self, slug: str, scope: str) -> None: ...
def pi_unload(self, slug: str, scope: str) -> None: ...
```

- Shell out with `[cli_path, "pi", "load|unload", slug, "--scope", scope,
  "--toolkit-repo", str(toolkit_root)]`.
- On non-zero exit, raise `RunnerError` with stderr first line.
- Return `None` on success (no payload needed; the caller re-invokes
  `pi_inventory` to learn the new state).

### 4.2 PiTabScreen bindings

Extend `PiTabScreen.BINDINGS` in `src/agent_toolkit_tui/app.py`:

```python
BINDINGS = [
    Binding("escape", "close", "Close"),
    Binding("q", "close", "Close"),
    Binding("u", "toggle_user", "User load/unload"),
    Binding("p", "toggle_project", "Project load/unload"),
]
```

Add `action_toggle_user` / `action_toggle_project`:

1. Get cursor row from the `DataTable` (`#pi-tab-table`). If no row is
   highlighted (e.g. empty table), update the footer with `"select a row
   first"` and return.
2. Look up the matching record in `self._records` by slug.
3. Decide load vs unload by the relevant `*_loaded` flag.
4. Call `self.runner.pi_load(slug, scope)` or `pi_unload(slug, scope)` (the
   screen needs a runner — pass it in via `__init__`, see 4.3).
5. On `RunnerError`, update the footer with the error and return without
   re-rendering.
6. On success: `self._records = self.runner.pi_inventory()`, then rebuild
   the table in place (clear rows, re-add from the refreshed list), preserve
   the cursor position by slug.

### 4.3 Plumbing the runner into the screen

`PiTabScreen.__init__` currently only takes `records`. Add a `runner:
CLIRunner` parameter so the screen can call back to the CLI. `TUIApp.action_show_pi_tab`
passes `self.runner` when pushing the screen.

### 4.4 Footer for errors / hints

Add a small `Static` (`id="pi-tab-footer"`) at the bottom of the modal's
`Vertical`. The two action methods write to it. Empty initially; cleared on
the next successful refresh.

### 4.5 Test

Add `tests/test_tui_pi_tab_bindings.py` with at least one Pilot test:

- Patch `CLIRunner.pi_inventory` to return a 1-row fixture (slug
  `status-bar`, `user_loaded=False`).
- Patch `CLIRunner.pi_load` to record the call and return `None`.
- Patch the second `pi_inventory` call to return the same row with
  `user_loaded=True`.
- Drive the app with `App.run_test` / `Pilot`, open the Pi modal (`8`),
  highlight row 0, press `u`.
- Assert `pi_load` was called with `("status-bar", "user")` and the
  rendered row now shows `✓` in the U column.

A second small unit test asserts `pi_load`/`pi_unload` shell-out shape (using
`monkeypatch` on `subprocess.run`) to mirror the existing pi_inventory
test.

## 5. Non-goals

- No new CLI verbs. `pi load` / `pi unload` already exist.
- No bulk toggle (multi-select). One row, one press.
- No new "diff/apply" pending model — Pi toggles are direct, unlike the main
  asset grid. (This matches the original spec's intent: Pi state is
  immediate write-through; `pi sync` is a no-op afterwards.)
- No global app-level `u`/`p` bindings.
- No undo: re-pressing the key inverts; that's the undo.

## 6. Risks

- **State drift between `_records` and the live filesystem after a partial
  failure.** Mitigation: always re-invoke `pi_inventory` after a successful
  toggle. On error, do *not* re-invoke — keep the user's view stable so they
  can read the error.
- **Cursor jumping after refresh.** Mitigation: record cursor slug before
  refresh, re-locate it after rebuilding rows.
- **Bindings firing on the wrong screen.** Mitigation: declare them on
  `PiTabScreen.BINDINGS`, not `TUIApp.BINDINGS` — Textual restricts screen
  bindings to that screen.

## 7. Files touched

- `src/agent_toolkit_tui/runner.py` — add `pi_load`, `pi_unload`.
- `src/agent_toolkit_tui/app.py` — extend `PiTabScreen` (bindings, actions,
  runner param, footer); pass `runner` in `action_show_pi_tab`.
- `src/agent_toolkit_tui/widgets/pi_tab.py` — remove the deferred-binding
  comment; the widget itself stays pure-data.
- `tests/test_tui_pi_tab_bindings.py` — new file with the Pilot + shell-out
  tests.
- (No CLI changes, no schema changes.)
