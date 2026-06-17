# Double Ctrl+C Quit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-subagent-driven-development (recommended) or superpowers-executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Claude Code / OpenCode-style double-ctrl+c quit behavior to `agent-toolkit-tui` without changing existing `q` quit semantics.

**Architecture:** Add one app-level key binding that overrides Textual's default ctrl+c `help_quit` action. Track the previous ctrl+c timestamp in `TUIApp`; first press notifies, second press inside the timeout delegates to existing `action_quit()` so pending-change confirmation remains centralized.

**Tech Stack:** Python, Textual, pytest/pytest-asyncio, `TUIApp.run_test()` pilot.

---

**Spec:** `docs/superpowers/specs/2026-06-17-441-double-ctrl-c-quit.md`
**Issue:** #441 · **Size:** M (feat)

## File structure

- Modify: `src/agent_toolkit_tui/app.py`
  - add timeout constant or class attribute;
  - add `ctrl+c` binding;
  - initialize timestamp state;
  - add `action_double_ctrl_c_quit()` that shows reminder on first press and calls `action_quit()` on timely second press.
- Create: `tests/test_tui/test_double_ctrl_c_quit.py`
  - focused async tests for first press, second press, timeout reset, pending-change delegation, and `q` regression.

## Task 1: Add focused tests first

**Files:**
- Create: `tests/test_tui/test_double_ctrl_c_quit.py`

- [ ] **Step 1: Write test scaffolding**

Use real `TUIApp`, not a subclass. Subclassing changes Textual CSS resolution for inherited `CSS_PATH = "css/app.tcss"` and can fail before behavior is tested. Monkeypatch instance methods instead:

```python
from __future__ import annotations

from types import MethodType

import pytest
from textual.widgets import DataTable

from agent_toolkit_tui.app import ConfirmDiscardScreen, TUIApp
from agent_toolkit_tui.widgets import SkillGrid


def spy_quit(app: TUIApp) -> list[str]:
    calls: list[str] = []

    def fake_action_quit(self: TUIApp) -> None:
        calls.append("quit")

    app.action_quit = MethodType(fake_action_quit, app)
    return calls


def spy_notify(app: TUIApp) -> list[str]:
    messages: list[str] = []
    original = app.notify

    def fake_notify(message: str, *args, **kwargs):  # noqa: ANN002, ANN003
        messages.append(message)
        return original(message, *args, **kwargs)

    app.notify = fake_notify
    return messages
```

- [ ] **Step 2: Write first-press reminder test**

```python
@pytest.mark.asyncio
async def test_ctrl_c_once_shows_reminder():
    app = TUIApp()
    quit_calls = spy_quit(app)
    notifications = spy_notify(app)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()

    assert quit_calls == []
    assert "Press ctrl+c again to quit" in notifications
```

Run: `uv run pytest tests/test_tui/test_double_ctrl_c_quit.py::test_ctrl_c_once_shows_reminder -q`
Expected: FAIL before implementation because ctrl+c is not bound to the new behavior.

- [ ] **Step 3: Write double-press quit test**

```python
@pytest.mark.asyncio
async def test_ctrl_c_twice_within_timeout_calls_quit():
    app = TUIApp()
    quit_calls = spy_quit(app)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.press("ctrl+c")
        await pilot.pause()

    assert quit_calls == ["quit"]
```

- [ ] **Step 4: Write timeout reset test**

Implementation imports `monotonic` into `agent_toolkit_tui.app`; monkeypatch that symbol so timing is deterministic:

```python
@pytest.mark.asyncio
async def test_ctrl_c_after_timeout_starts_fresh(monkeypatch):
    times = iter([100.0, 102.0])
    monkeypatch.setattr("agent_toolkit_tui.app.monotonic", lambda: next(times))

    app = TUIApp()
    quit_calls = spy_quit(app)
    notifications = spy_notify(app)

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.press("ctrl+c")
        await pilot.pause()

    assert quit_calls == []
    assert notifications == [
        "Press ctrl+c again to quit",
        "Press ctrl+c again to quit",
    ]
```

- [ ] **Step 5: Write `q` regression test with table focus**

The app starts with `#skill-filter` focused; plain `q` is intentionally text input there. Focus the table to test the existing app-level `q` quit binding:

```python
@pytest.mark.asyncio
async def test_q_still_uses_existing_quit_action_with_table_focus():
    app = TUIApp()
    quit_calls = spy_quit(app)

    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#skill-table", DataTable).focus()
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()

    assert quit_calls == ["quit"]
```

- [ ] **Step 6: Write pending-change confirmation test**

Use a counted existing grid (`SkillGrid`) because `action_quit()` currently counts instruction/skill/pi/agent pending entries. Do not test MCP here; adding MCP to `action_quit()` is an existing separate gap, not part of this ctrl+c binding issue.

```python
@pytest.mark.asyncio
async def test_ctrl_c_double_uses_existing_pending_confirm_screen():
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        skill_grid.restore_pending({("project", "standard", "demo"): "link"})

        await pilot.press("ctrl+c")
        await pilot.press("ctrl+c")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDiscardScreen)
```

Run all new tests:
`uv run pytest tests/test_tui/test_double_ctrl_c_quit.py -q`
Expected: first/double/timeout/pending tests fail before implementation.

## Task 2: Implement app binding and state

**Files:**
- Modify: `src/agent_toolkit_tui/app.py`

- [ ] **Step 1: Import monotonic**

```python
from time import monotonic
```

- [ ] **Step 2: Add timeout constant near asset labels or inside `TUIApp`**

```python
_DOUBLE_CTRL_C_QUIT_SECONDS = 1.5
```

- [ ] **Step 3: Add binding**

In `TUIApp.BINDINGS`, add before `q` so footer displays both quit paths cleanly:

```python
Binding("ctrl+c", "double_ctrl_c_quit", "Quit", priority=True),
```

- [ ] **Step 4: Add timestamp state**

In `TUIApp.__init__`:

```python
self._last_ctrl_c_quit_at: float | None = None
```

- [ ] **Step 5: Add action**

Near `action_quit`:

```python
def action_double_ctrl_c_quit(self) -> None:
    now = monotonic()
    last = self._last_ctrl_c_quit_at
    if last is not None and now - last <= _DOUBLE_CTRL_C_QUIT_SECONDS:
        self._last_ctrl_c_quit_at = None
        self.action_quit()
        return

    self._last_ctrl_c_quit_at = now
    self.notify("Press ctrl+c again to quit")
```

- [ ] **Step 6: Run focused tests**

Run: `uv run pytest tests/test_tui/test_double_ctrl_c_quit.py -q`
Expected: PASS.

## Task 3: Regression checks

**Files:**
- No additional files unless tests reveal existing fixture issue.

- [ ] **Step 1: Run TUI test slice**

Run: `uv run pytest tests/test_tui -q`
Expected: PASS.

- [ ] **Step 2: Run whole suite if time budget permits**

Run: `uv run pytest -q`
Expected: PASS or report unrelated existing failures with evidence.

- [ ] **Step 3: Check lint/format for touched files**

Run: `uv run ruff check src/agent_toolkit_tui/app.py tests/test_tui/test_double_ctrl_c_quit.py`
Expected: PASS.

## Verification / rungs

R0 unit. Capture evidence under `assets/verification/0/` per project test-plane convention if executing this plan via `/aj-run`: focused test output, TUI slice output, ruff output, and whole-suite output if run.

User-facing surface: TUI keybinding behavior. Written visual judgment required if demoing manually: first ctrl+c shows notification text; second ctrl+c exits or shows pending-confirm screen.

## Commit shape

One implementation commit on the feature branch:

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui/test_double_ctrl_c_quit.py
git cm "feat(tui): support double ctrl-c quit"
```

PR title: `feat(tui): support double ctrl+c quit`.
