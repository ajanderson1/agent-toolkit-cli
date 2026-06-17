# Spec — #441 double-ctrl+c quit in TUI

**Issue:** #441 · **Size:** M (feat) · **Date:** 2026-06-17

## Problem

`agent-toolkit-tui` has no ctrl+c quit path. Textual's default ctrl+c handling triggers `help_quit`, which tells users to press the app's quit key (`q`). Users coming from Claude Code or OpenCode often press ctrl+c twice to exit; today that reflex lands on a hint rather than a quit path.

## User-facing behavior

- First ctrl+c press shows: `Press ctrl+c again to quit`.
- Second ctrl+c press within 1.5 seconds routes through the existing quit flow.
- If no pending changes exist, the second press exits the app.
- If pending changes exist, the second press opens the existing `ConfirmDiscardScreen` rather than bypassing safety.
- If more than 1.5 seconds elapse after the first press, the next ctrl+c is treated as a fresh first press.
- Existing `q` → `action_quit` behavior stays unchanged.

## Approach

Add an explicit `ctrl+c` binding on `TUIApp` that overrides Textual's default `help_quit` binding. The binding should target a new app action, not `action_quit` directly, because the first press must show a reminder rather than quit.

Implementation shape:

- Add `Binding("ctrl+c", "double_ctrl_c_quit", "Quit", priority=True)` to `TUIApp.BINDINGS`.
- Add a module/class constant for the timeout (`1.5` seconds).
- Add one timestamp field to `TUIApp.__init__`, initialized to `None`.
- Implement `action_double_ctrl_c_quit()`:
  - read a monotonic timestamp;
  - if previous timestamp exists and delta is <= 1.5 seconds, clear timestamp and call `self.action_quit()`;
  - otherwise store current timestamp and call `self.notify("Press ctrl+c again to quit")`.
- Do not duplicate pending-change logic. The second ctrl+c must call `action_quit()` so the existing `ConfirmDiscardScreen` behavior remains the single source of truth.

## Acceptance criteria

- [ ] Pressing ctrl+c once shows `Press ctrl+c again to quit`.
- [ ] Pressing ctrl+c twice within 1.5 seconds calls the existing quit path.
- [ ] Pressing ctrl+c once, waiting more than 1.5 seconds, then pressing ctrl+c again does not quit and refreshes the reminder.
- [ ] Existing `q` quit behavior remains unchanged.
- [ ] Pending changes still trigger `ConfirmDiscardScreen` on the second ctrl+c.
- [ ] No runtime dependency, schema, API contract, or published CLI behavior changes.

## Out of scope

- Rebinding ctrl+c to copy inside focused inputs.
- Changing `q` behavior or quit confirmation copy.
- Adding ctrl+c behavior to non-TUI CLI commands.
- Introducing configurable timeout settings.
- Fixing the unrelated current gap where `action_quit()` counts instruction/skill/pi/agent pending entries but not MCP pending entries.

## Test surface

- New TUI app tests under `tests/test_tui/` covering:
  - single ctrl+c reminder notification;
  - double ctrl+c within 1.5 seconds calls `action_quit`;
  - expired timer treats next ctrl+c as first press;
  - pending changes on a currently counted grid route through existing quit confirmation via `action_quit`;
  - `q` path remains unchanged when focus is on a non-input surface.
- Focused command: `uv run pytest tests/test_tui/test_double_ctrl_c_quit.py -q`.
- Regression command: `uv run pytest tests/test_tui -q`.

## Classification

**Size: M** — implementation is small, but the build plan touches two files (`src/agent_toolkit_tui/app.py` and a new TUI test file). That fails the `S` safeguard (single touched file), so the issue is bumped from S to M. No L risk signals apply: no new dependency, schema/migration, auth/secrets, published interface break, top-level directory, or strategy change.

## Critical review

- ✓ Resolved: initial plan proposed a `TUIApp` subclass for tests; reviewer found Textual CSS resolution can fail for subclasses. Plan now uses real `TUIApp` instances with monkeypatched methods.
- ✓ Resolved: initial `q` regression ignored startup focus on `#skill-filter`; plan now focuses `#skill-table` before pressing `q`.
- ✓ Resolved: initial pending-confirm test only spied `action_quit`; plan now creates a `SkillGrid` pending entry and asserts `ConfirmDiscardScreen` is active.
- ✓ Resolved: reviewer noted existing MCP pending entries are not counted by `action_quit`; spec marks that as out of scope for this ctrl+c binding change.
