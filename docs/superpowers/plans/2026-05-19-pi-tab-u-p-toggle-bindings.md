# Pi Tab u/p Toggle Bindings — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `u`/`p` key bindings on the TUI's `PiTabScreen` so the operator can load/unload Pi extensions per-scope from the inventory modal, with refresh and error feedback.

**Architecture:** Add `pi_load` / `pi_unload` shell-outs to `CLIRunner` (mirroring `pi_inventory`). Pass the runner into `PiTabScreen` so its screen-scoped `BINDINGS` can route `u` → user-scope toggle and `p` → project-scope toggle, deciding load vs unload by the row's current `*_loaded` flag. After a successful toggle, re-invoke `pi_inventory` and rebuild the `DataTable` in place; on failure, surface a one-liner in a modal footer without crashing.

**Tech Stack:** Python 3.x, Textual (DataTable, ModalScreen, Binding, Pilot), `subprocess` shell-outs, pytest + `pytest-asyncio` (for `App.run_test`).

---

## File Structure

- `src/agent_toolkit_tui/runner.py` — add `pi_load(slug, scope)` and `pi_unload(slug, scope)` methods (same pattern as `pi_inventory`, `__init__`/`subprocess.run`/`RunnerError`).
- `src/agent_toolkit_tui/app.py` — extend `PiTabScreen`:
  - Accept `runner: CLIRunner` in `__init__`.
  - Add `u`/`p` bindings.
  - Add `action_toggle_user` and `action_toggle_project`.
  - Add a `Static#pi-tab-footer` to the modal compose.
  - `TUIApp.action_show_pi_tab` passes `self.runner` to the screen.
- `src/agent_toolkit_tui/widgets/pi_tab.py` — remove the "deferred bindings" comment (module docstring + class docstring).
- `tests/test_tui_pi_tab_bindings.py` — new: unit test for runner shell-out shape; Pilot test for the press-`u` happy path.

---

## Task 1: Runner — `pi_load` and `pi_unload`

**Files:**
- Modify: `src/agent_toolkit_tui/runner.py` (add two methods after `pi_inventory`, before the `# ----- writes -----` divider so they sit with the pi read/write group)
- Test: `tests/test_tui_pi_tab_bindings.py` (new file)

- [ ] **Step 1: Create the new test file with two failing runner tests**

Create `tests/test_tui_pi_tab_bindings.py`:

```python
"""Tests for the Pi tab u/p toggle bindings.

Two surfaces:
1. CLIRunner.pi_load / pi_unload shell-out shape (subprocess mocked).
2. PiTabScreen press-u happy path (Pilot, runner mocked).
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from agent_toolkit_tui.runner import CLIRunner, RunnerError


# --- runner shell-out shape -------------------------------------------------

def _make_runner(tmp_path: Path) -> CLIRunner:
    return CLIRunner(toolkit_root=tmp_path, cli_path=Path("agent-toolkit-cli"))


def test_pi_load_invokes_cli_with_scope_and_toolkit_repo(monkeypatch, tmp_path):
    captured: dict[str, Any] = {}

    def fake_run(cmd, capture_output, text, check):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = _make_runner(tmp_path)
    runner.pi_load("status-bar", "user")

    assert captured["cmd"][1:] == [
        "pi", "load", "status-bar",
        "--scope", "user",
        "--toolkit-repo", str(tmp_path),
    ]


def test_pi_unload_invokes_cli_with_scope_and_toolkit_repo(monkeypatch, tmp_path):
    captured: dict[str, Any] = {}

    def fake_run(cmd, capture_output, text, check):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = _make_runner(tmp_path)
    runner.pi_unload("status-bar", "project")

    assert captured["cmd"][1:] == [
        "pi", "unload", "status-bar",
        "--scope", "project",
        "--toolkit-repo", str(tmp_path),
    ]


def test_pi_load_nonzero_exit_raises_runner_error(monkeypatch, tmp_path):
    def fake_run(cmd, capture_output, text, check):
        return subprocess.CompletedProcess(
            cmd, returncode=2, stdout="", stderr="boom: missing slug\n"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = _make_runner(tmp_path)
    with pytest.raises(RunnerError) as excinfo:
        runner.pi_load("nope", "user")
    assert "boom: missing slug" in str(excinfo.value)
```

- [ ] **Step 2: Run the three runner tests — expect ImportError / AttributeError**

Run: `uv run pytest tests/test_tui_pi_tab_bindings.py -v`
Expected: tests fail because `pi_load` / `pi_unload` are not defined on `CLIRunner`.

- [ ] **Step 3: Implement `pi_load` and `pi_unload` on `CLIRunner`**

In `src/agent_toolkit_tui/runner.py`, immediately after the `pi_inventory` method (around line 107, before the `# ----- writes -----` divider on line ~109), add:

```python
    def pi_load(self, slug: str, scope: str) -> None:
        """Invoke `pi load <slug> --scope <scope>`. Raise RunnerError on non-zero exit."""
        proc = subprocess.run(
            [str(self.cli_path), "pi", "load", slug,
             "--scope", scope,
             "--toolkit-repo", str(self.toolkit_root)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            raise RunnerError(
                f"pi load {slug} --scope {scope} exited {proc.returncode}: "
                f"{proc.stderr.strip()}"
            )

    def pi_unload(self, slug: str, scope: str) -> None:
        """Invoke `pi unload <slug> --scope <scope>`. Raise RunnerError on non-zero exit."""
        proc = subprocess.run(
            [str(self.cli_path), "pi", "unload", slug,
             "--scope", scope,
             "--toolkit-repo", str(self.toolkit_root)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            raise RunnerError(
                f"pi unload {slug} --scope {scope} exited {proc.returncode}: "
                f"{proc.stderr.strip()}"
            )
```

- [ ] **Step 4: Run the three runner tests — expect PASS**

Run: `uv run pytest tests/test_tui_pi_tab_bindings.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/runner.py tests/test_tui_pi_tab_bindings.py
git commit -m "feat(tui): CLIRunner.pi_load / pi_unload shell-outs (#107)"
```

---

## Task 2: PiTabScreen — accept runner; add `u`/`p` bindings + actions + footer

**Files:**
- Modify: `src/agent_toolkit_tui/app.py` (`PiTabScreen` class around lines 91-130; `action_show_pi_tab` around lines 254-267)
- Test: `tests/test_tui_pi_tab_bindings.py` (append a Pilot test)

- [ ] **Step 1: Write the Pilot happy-path test**

Append to `tests/test_tui_pi_tab_bindings.py`:

```python
# --- PiTabScreen Pilot ------------------------------------------------------

@pytest.mark.asyncio
async def test_pressing_u_loads_under_user_scope_and_refreshes(monkeypatch, tmp_path):
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.runner import CLIRunner

    # Two inventory snapshots: before and after the user-scope load.
    record_before = {
        "slug": "status-bar",
        "origin": "first-party",
        "source": "extension:status-bar",
        "user_loaded": False,
        "project_loaded": False,
        "toolkit_intent": "user",
    }
    record_after = dict(record_before, user_loaded=True)

    inventories = iter([[record_before], [record_after]])

    load_calls: list[tuple[str, str]] = []

    def fake_pi_inventory(self):
        return next(inventories)

    def fake_pi_load(self, slug, scope):
        load_calls.append((slug, scope))

    monkeypatch.setattr(CLIRunner, "pi_inventory", fake_pi_inventory)
    monkeypatch.setattr(CLIRunner, "pi_load", fake_pi_load)
    # Minimal list_state stub so TUIApp.__init__ doesn't fail.
    monkeypatch.setattr(
        CLIRunner, "list_state",
        lambda self: {"assets": [], "links": {"user": {}, "project": {}}},
    )

    app = TUIApp(toolkit_root=tmp_path)
    async with app.run_test() as pilot:
        # Open the Pi modal.
        await pilot.press("8")
        await pilot.pause()
        # Highlight row 0 is the default cursor position; press u.
        await pilot.press("u")
        await pilot.pause()

        assert load_calls == [("status-bar", "user")]

        # The table should now show ✓ in the U column for the only row.
        from textual.widgets import DataTable
        table = app.screen.query_one("#pi-tab-table", DataTable)
        row = table.get_row_at(0)
        # Column order: Slug, Origin, U, P, Intent, Source.
        assert row[0] == "status-bar"
        assert row[2] == "✓"
```

- [ ] **Step 2: Run the Pilot test — expect FAIL**

Run: `uv run pytest tests/test_tui_pi_tab_bindings.py::test_pressing_u_loads_under_user_scope_and_refreshes -v`
Expected: failure — either `PiTabScreen` rejects the unexpected `runner` arg in `__init__` (after Step 3 below introduces it) or the press-`u` action doesn't exist.

- [ ] **Step 3: Extend `PiTabScreen` to accept a runner and add `u`/`p` bindings + actions + footer**

In `src/agent_toolkit_tui/app.py`, replace the `PiTabScreen` class (currently lines ~91-130) with:

```python
class PiTabScreen(ModalScreen[None]):
    """Modal screen that hosts the Pi inventory view with u/p toggles.

    Press ``escape`` or ``q`` to dismiss. With a row highlighted, press
    ``u`` to toggle user-scope load state and ``p`` for project-scope.
    """

    DEFAULT_CSS = """
    PiTabScreen {
        align: center middle;
    }
    PiTabScreen > Vertical {
        background: $panel;
        border: thick $primary;
        padding: 1 2;
        width: 90%;
        height: 80%;
    }
    PiTabScreen Label {
        text-style: bold;
        margin-bottom: 1;
    }
    PiTabScreen #pi-tab-footer {
        margin-top: 1;
        color: $warning;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
        Binding("u", "toggle_user", "User load/unload"),
        Binding("p", "toggle_project", "Project load/unload"),
    ]

    def __init__(self, records: list[dict], runner: "CLIRunner") -> None:
        super().__init__()
        self._records = records
        self._runner = runner

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Pi extension inventory — {len(self._records)} record(s)")
            yield PiTab(records=self._records, id="pi-tab")
            yield Static("", id="pi-tab-footer")

    def action_close(self) -> None:
        self.dismiss(None)

    def action_toggle_user(self) -> None:
        self._toggle("user")

    def action_toggle_project(self) -> None:
        self._toggle("project")

    def _toggle(self, scope: str) -> None:
        from textual.widgets import DataTable  # local import: avoids top-level churn
        try:
            table = self.query_one("#pi-tab-table", DataTable)
        except Exception:
            self._set_footer("no table to act on")
            return
        cursor = table.cursor_row
        if cursor is None or cursor < 0 or cursor >= len(self._records):
            self._set_footer("select a row first")
            return
        record = self._records[cursor]
        slug = record.get("slug", "")
        if not slug:
            self._set_footer("row has no slug")
            return
        flag = "user_loaded" if scope == "user" else "project_loaded"
        try:
            if record.get(flag):
                self._runner.pi_unload(slug, scope)
            else:
                self._runner.pi_load(slug, scope)
        except Exception as exc:
            self._set_footer(f"pi {scope} toggle error: {exc}")
            return
        # Refresh inventory and rebuild the table in place.
        try:
            new_records = self._runner.pi_inventory()
        except Exception as exc:
            self._set_footer(f"refresh error: {exc}")
            return
        self._records = new_records
        self._rebuild_table(table, prefer_slug=slug)
        self._set_footer("")

    def _rebuild_table(self, table, prefer_slug: str) -> None:
        table.clear()
        new_cursor = 0
        for idx, r in enumerate(self._records):
            badge = "1P" if r.get("origin") == "first-party" else "3P"
            table.add_row(
                r.get("slug", ""),
                badge,
                "✓" if r.get("user_loaded") else " ",
                "✓" if r.get("project_loaded") else " ",
                r.get("toolkit_intent", ""),
                r.get("source", ""),
            )
            if r.get("slug") == prefer_slug:
                new_cursor = idx
        if self._records:
            table.move_cursor(row=new_cursor)

    def _set_footer(self, msg: str) -> None:
        try:
            self.query_one("#pi-tab-footer", Static).update(msg)
        except Exception:
            pass
```

Also update `TUIApp.action_show_pi_tab` (around lines 254-267) to pass the runner:

```python
        self.push_screen(PiTabScreen(records=records, runner=self.runner))
```

If `CLIRunner` is not already imported at the top of `app.py`, ensure the existing `from .runner import CLIRunner, RunnerError` (it is — check at the top) covers the new type reference.

- [ ] **Step 4: Run the Pilot test — expect PASS**

Run: `uv run pytest tests/test_tui_pi_tab_bindings.py -v`
Expected: 4 passed (3 runner + 1 Pilot).

- [ ] **Step 5: Run the full TUI test suite to catch regressions**

Run: `uv run pytest tests/ -k "tui or pi" -v`
Expected: all green. In particular, the previously-existing `tests/test_tui_pi_tab.py` (`PiTab` widget pure-data tests) should still pass — the widget itself is unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui/app.py tests/test_tui_pi_tab_bindings.py
git commit -m "feat(tui): u/p toggle bindings on PiTabScreen (#107)"
```

---

## Task 3: Remove the deferred-binding comment from `pi_tab.py`

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/pi_tab.py` (module docstring lines 8-12; class docstring lines 22-25)

- [ ] **Step 1: Drop the deferred-binding paragraph from the module docstring**

In `src/agent_toolkit_tui/widgets/pi_tab.py`, replace:

```python
"""Pi tab — Textual widget consuming `agent-toolkit-cli pi inventory --format json`.

Pure-data widget: receives records via constructor, exposes `rows()` for
testing without spinning up the whole Textual app. The app shells out to
``agent-toolkit-cli pi inventory --format json`` and passes the parsed
records into this widget for display.

Toggle key bindings (``u``/``p``) are intentionally not wired in this commit
— the spec ranks the read-only inventory view higher than toggle behaviour,
and a later commit can add them once the broader binding plumbing is in
place. See plan: docs/superpowers/plans/2026-05-19-pi-unified-extension-inventory.md.
"""
```

with:

```python
"""Pi tab — Textual widget consuming `agent-toolkit-cli pi inventory --format json`.

Pure-data widget: receives records via constructor, exposes `rows()` for
testing without spinning up the whole Textual app. The app shells out to
``agent-toolkit-cli pi inventory --format json`` and passes the parsed
records into this widget for display. Load/unload toggles live on the
hosting `PiTabScreen` (`u` / `p`); this widget remains pure rendering.
"""
```

And in the class docstring, replace:

```python
    """Pi extension inventory display.

    Read-only for now — toggle bindings deferred to a follow-up commit.
    """
```

with:

```python
    """Pi extension inventory display (pure rendering)."""
```

- [ ] **Step 2: Run the existing widget tests**

Run: `uv run pytest tests/test_tui_pi_tab.py -v`
Expected: existing 3 tests pass — the widget's behaviour is unchanged.

- [ ] **Step 3: Commit**

```bash
git add src/agent_toolkit_tui/widgets/pi_tab.py
git commit -m "docs(tui): drop deferred-bindings note from pi_tab widget (#107)"
```

---

## Task 4: Final verification — full suite green

- [ ] **Step 1: Run the full pytest suite**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 2: Lint pass**

Run: `uv run ruff check src tests` (or whatever the repo's ruff invocation is — check `lefthook.yml`)
Expected: clean.

- [ ] **Step 3: Confirm git log shows the three feature commits**

Run: `git log --oneline -5`
Expected: three feature commits (Task 1, 2, 3) on top of the spec commit.

No commit at this step — Task 4 is verification only.

---

## Self-review

- **Spec coverage:** Runner (4.1) → Task 1. Bindings + actions + refresh (4.2) → Task 2. Runner plumbed into screen (4.3) → Task 2 step 3. Footer (4.4) → Task 2 step 3 (CSS + compose + `_set_footer`). Pilot test (4.5) → Task 2 step 1; runner shell-out tests → Task 1 step 1. Deferred-binding comment removal → Task 3. Acceptance criteria (1)–(6) all map to either the Pilot test (1, 3, 5, 6 via screen-scoped bindings) or to the runner shell-out test (4 indirectly: `RunnerError` raised on non-zero).
- **Placeholder scan:** No "TBD" / "implement later" / "Similar to Task N". Every code-touching step has the actual code.
- **Type consistency:** `PiTabScreen.__init__(records, runner)` is the same signature used in Task 2 step 3 and in the `TUIApp.action_show_pi_tab` call site. Runner methods `pi_load(slug, scope)` and `pi_unload(slug, scope)` have the same signature in Task 1 (definition + runner tests) and Task 2 (`_toggle` callers + Pilot mock).
- **Note on acceptance criterion 4 (error → footer, no crash):** Covered by the `except Exception` blocks in `_toggle`; the runner-level RunnerError test (`test_pi_load_nonzero_exit_raises_runner_error`) verifies the exception path is real. If the reviewer wants a dedicated screen-level error test, that's a small follow-up — not blocking.
