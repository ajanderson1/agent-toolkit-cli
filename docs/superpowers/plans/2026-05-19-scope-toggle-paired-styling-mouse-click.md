# Scope Toggle — Paired Styling + Working Mouse Click — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `Static` + Rich `[@click=…]` chip markup in the TUI content header with a small dedicated `ScopeToggle` widget so the two scope options share a single paired-toggle visual and clicks via the mouse actually flip the active scope.

**Architecture:** A new `ScopeToggle` widget (subclass of `Horizontal`) is composed inside the existing `#content` Vertical, alongside (and to the right of) the kind label + count text. The toggle owns two `Label` widgets — one per scope — each with an explicit `on_click` handler that calls `self.app.action_scope("project" | "user")`. The content-header `Static` shrinks back to "kind label + count" only; the scope chips are no longer Rich markup. Active vs inactive is signalled by CSS classes (`-active` / `-inactive`) — both labels carry the same shape, padding, and border treatment; only the background/foreground colour distinguishes them. No `[dim]`, no `[reverse]`. The keyboard `s` binding and `action_scope` / `action_scope_toggle` methods are unchanged.

**Tech Stack:** Python 3, Textual (TUI framework), pytest + textual.pilot for tests, Rich markup for the residual non-scope header text.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/agent_toolkit_tui/widgets/scope_toggle.py` | New `ScopeToggle` widget. Renders two `Label`s, dispatches clicks to `app.action_scope`, exposes `set_active(scope)`. | **Create** |
| `src/agent_toolkit_tui/widgets/__init__.py` | Export `ScopeToggle`. | **Modify** |
| `src/agent_toolkit_tui/app.py` | Compose `ScopeToggle` next to the content header; drop scope chips from `_build_content_header`; have `action_scope` notify the toggle to repaint. | **Modify** (lines `127-128`, `185-195`, `283-304`, `306-312`) |
| `src/agent_toolkit_tui/css/app.tcss` | Add CSS rules for `ScopeToggle` and its `Label` children in both active and inactive states. | **Modify** (append, ~line 68) |
| `tests/test_tui/test_app.py` | Update existing scope-toggle tests to drive the new widget; add a real `pilot.click` test that exercises mouse hit-testing. | **Modify** (lines `677-727` plus new test) |
| `tests/test_tui/test_scope_toggle.py` | Unit-level tests for the new widget in isolation. | **Create** |

The new widget lives in `widgets/` alongside `asset_grid.py` and `kinds_sidebar.py` to match the existing pattern. Naming convention: snake_case file, PascalCase class.

---

## Task 1: Add the failing test for the new ScopeToggle widget

**Files:**
- Test: `tests/test_tui/test_scope_toggle.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_tui/test_scope_toggle.py` with:

```python
"""Unit tests for ScopeToggle — paired-toggle widget for the TUI content header.

These tests exercise the widget in isolation (no app, no runner) to lock its
contract: it composes two labels, exposes set_active(scope), and dispatches
clicks to the app's action_scope action.
"""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Label

from agent_toolkit_tui.widgets import ScopeToggle


class _Host(App):
    """Minimal host app so the widget can be mounted in a pilot."""

    def __init__(self) -> None:
        super().__init__()
        self.scope_calls: list[str] = []

    def compose(self) -> ComposeResult:
        yield ScopeToggle(active="project", id="scope-toggle")

    def action_scope(self, scope: str) -> None:
        self.scope_calls.append(scope)


@pytest.mark.asyncio
async def test_scope_toggle_renders_both_labels():
    """ScopeToggle composes one Label per scope value (project, user)."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        labels = list(app.query(ScopeToggle).first().query(Label))
        texts = {str(label.renderable).strip() for label in labels}
        assert texts == {"project", "user"}


@pytest.mark.asyncio
async def test_scope_toggle_set_active_marks_classes():
    """set_active(scope) flips the -active / -inactive classes on each label."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        toggle = app.query_one(ScopeToggle)

        toggle.set_active("user")
        await pilot.pause()
        project_label = toggle.query_one("#scope-toggle-project", Label)
        user_label = toggle.query_one("#scope-toggle-user", Label)
        assert "-active" in user_label.classes
        assert "-inactive" in project_label.classes
        assert "-active" not in project_label.classes
        assert "-inactive" not in user_label.classes


@pytest.mark.asyncio
async def test_scope_toggle_click_dispatches_action_scope():
    """Clicking a scope label calls app.action_scope with that scope name."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Click the inactive ('user') label directly.
        await pilot.click("#scope-toggle-user")
        await pilot.pause()
        assert app.scope_calls == ["user"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_scope_toggle.py -v`
Expected: FAIL — `ImportError: cannot import name 'ScopeToggle' from 'agent_toolkit_tui.widgets'`.

- [ ] **Step 3: No implementation yet** — Task 2 creates the widget. Do not commit yet; the failing test will be committed alongside the implementation in Task 2 step 5.

---

## Task 2: Implement the ScopeToggle widget

**Files:**
- Create: `src/agent_toolkit_tui/widgets/scope_toggle.py`
- Modify: `src/agent_toolkit_tui/widgets/__init__.py`

- [ ] **Step 1: Read current widgets/__init__.py**

Run: `cat src/agent_toolkit_tui/widgets/__init__.py`
Expected output (verbatim — match before editing):

```python
"""TUI widgets package."""
from agent_toolkit_tui.widgets.asset_grid import AssetGrid
from agent_toolkit_tui.widgets.kinds_sidebar import KindsSidebar

__all__ = ["AssetGrid", "KindsSidebar"]
```

If the current contents differ, adapt the edit in Step 3 to preserve whatever is there.

- [ ] **Step 2: Create `src/agent_toolkit_tui/widgets/scope_toggle.py`**

```python
"""ScopeToggle — paired-toggle widget for scope=project|user in the content header.

Replaces the old Rich [@click=…] markup chips that were embedded in
#content-header. Each scope is rendered as a Label with an explicit on_click
handler, so mouse hit-testing is unambiguous and we don't depend on Rich
action-link parsing inside a Static.
"""
from __future__ import annotations

from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label

SCOPES: tuple[str, ...] = ("project", "user")


class ScopeToggle(Horizontal):
    """Two-state toggle between 'project' and 'user' scopes.

    Composition: a Horizontal of two Labels, one per scope value. Active state
    is signalled via CSS class names (-active / -inactive) — both labels share
    the same shape and padding; only colour distinguishes them.

    Click handling: each Label's on_click handler dispatches to
    `self.app.action_scope(scope)`. The host app owns the scope state machine;
    this widget is a pure view + click-source.
    """

    DEFAULT_CSS: ClassVar[str] = ""

    def __init__(self, *, active: str = "project", id: str | None = None) -> None:
        super().__init__(id=id)
        if active not in SCOPES:
            raise ValueError(f"active must be one of {SCOPES}, got {active!r}")
        self._active: str = active
        self._toggle_id: str = id or "scope-toggle"

    def compose(self) -> ComposeResult:
        yield Label("scope:", classes="scope-toggle-label")
        for scope in SCOPES:
            label = Label(
                scope,
                id=f"{self._toggle_id}-{scope}",
                classes="scope-option " + ("-active" if scope == self._active else "-inactive"),
            )
            yield label

    def set_active(self, scope: str) -> None:
        """Re-paint to mark `scope` as active, the other as inactive."""
        if scope not in SCOPES:
            raise ValueError(f"scope must be one of {SCOPES}, got {scope!r}")
        self._active = scope
        for s in SCOPES:
            try:
                label = self.query_one(f"#{self._toggle_id}-{s}", Label)
            except Exception:
                continue
            label.remove_class("-active")
            label.remove_class("-inactive")
            label.add_class("-active" if s == scope else "-inactive")

    def on_click(self, event: events.Click) -> None:
        """Dispatch when a child Label is clicked.

        Textual bubbles the Click event up from the Label to this Horizontal.
        We identify the source by the event.widget.id and route to
        self.app.action_scope.
        """
        target = event.widget
        if target is None:
            return
        widget_id = getattr(target, "id", None)
        if not widget_id or not widget_id.startswith(f"{self._toggle_id}-"):
            return
        scope = widget_id[len(self._toggle_id) + 1 :]
        if scope not in SCOPES:
            return
        event.stop()
        self.app.action_scope(scope)
```

- [ ] **Step 3: Export from widgets/__init__.py**

Edit `src/agent_toolkit_tui/widgets/__init__.py`. Replace the file with:

```python
"""TUI widgets package."""
from agent_toolkit_tui.widgets.asset_grid import AssetGrid
from agent_toolkit_tui.widgets.kinds_sidebar import KindsSidebar
from agent_toolkit_tui.widgets.scope_toggle import ScopeToggle

__all__ = ["AssetGrid", "KindsSidebar", "ScopeToggle"]
```

- [ ] **Step 4: Run scope_toggle tests; verify they pass**

Run: `uv run pytest tests/test_tui/test_scope_toggle.py -v`
Expected: 3 passed.

If `test_scope_toggle_click_dispatches_action_scope` fails because Textual's `pilot.click` doesn't bubble through the way we expect, fall back to overriding `on_click` on the Label children directly (give each Label its own handler that calls `self.app.action_scope(<its-scope>)`). The widget interface (`set_active`, two child Labels with the right ids) stays the same.

- [ ] **Step 5: Commit Tasks 1 + 2 together**

```bash
git add tests/test_tui/test_scope_toggle.py src/agent_toolkit_tui/widgets/scope_toggle.py src/agent_toolkit_tui/widgets/__init__.py
git commit -m "feat(#99): add ScopeToggle widget for paired scope chips"
```

---

## Task 3: CSS — paired-toggle visual

**Files:**
- Modify: `src/agent_toolkit_tui/css/app.tcss`

- [ ] **Step 1: Read the current `#content-header` rule**

Run: `sed -n '60,75p' src/agent_toolkit_tui/css/app.tcss`
Expected output (verbatim):

```
#content-header {
    height: auto;
    color: $text;
    padding: 0 0 1 0;
    border-bottom: tall $primary-darken-2;
    margin: 0 0 1 0;
}
```

- [ ] **Step 2: Append new CSS rules at the end of the file**

```css

/* Scope toggle — paired toggle between project and user, replaces old
   Rich [@click=...] chip markup. Both options share padding + border;
   only background/foreground distinguishes active from inactive. */
ScopeToggle {
    height: 1;
    width: auto;
    margin: 0 0 0 2;
}

ScopeToggle Label.scope-toggle-label {
    color: $text-muted;
    margin: 0 1 0 0;
}

ScopeToggle Label.scope-option {
    padding: 0 1;
    margin: 0;
    background: $surface;
    color: $text;
    border-left: vkey $primary-darken-2;
}

ScopeToggle Label.scope-option.-active {
    background: $accent;
    color: $background;
    text-style: bold;
}

ScopeToggle Label.scope-option.-inactive {
    background: $surface;
    color: $text;
    text-style: none;
}
```

- [ ] **Step 3: No test step here** — CSS is verified by the end-to-end app test in Task 5.

- [ ] **Step 4: Commit**

```bash
git add src/agent_toolkit_tui/css/app.tcss
git commit -m "feat(#99): CSS for ScopeToggle paired-toggle visual"
```

---

## Task 4: Wire ScopeToggle into the app; drop chips from `_build_content_header`

**Files:**
- Modify: `src/agent_toolkit_tui/app.py`

- [ ] **Step 1: Read the current `compose`, `action_scope`, and `_build_content_header` regions**

Run:
```bash
sed -n '120,135p' src/agent_toolkit_tui/app.py
sed -n '183,205p' src/agent_toolkit_tui/app.py
sed -n '280,315p' src/agent_toolkit_tui/app.py
```

Confirm the regions match the spec line ranges (`127-128`, `185-195`, `283-304`, `306-312`). If line numbers have drifted, locate by content — the edits below identify the exact strings.

- [ ] **Step 2: Add the import**

Find this line near the top of `src/agent_toolkit_tui/app.py`:

```python
from agent_toolkit_tui.widgets import AssetGrid, KindsSidebar
```

Replace with:

```python
from agent_toolkit_tui.widgets import AssetGrid, KindsSidebar, ScopeToggle
```

- [ ] **Step 3: Compose the toggle next to the content header**

Find this block in the `compose` method:

```python
            with Vertical(id="content"):
                yield Static(self._build_content_header(), id="content-header")
                yield AssetGrid(self.state, id="asset-grid")
```

Replace with:

```python
            with Vertical(id="content"):
                with Horizontal(id="content-header-row"):
                    yield Static(self._build_content_header(), id="content-header")
                    yield ScopeToggle(active=self._scope, id="scope-toggle")
                yield AssetGrid(self.state, id="asset-grid")
```

- [ ] **Step 4: Drop chips from `_build_content_header`**

Replace the entire `_build_content_header` method:

```python
    def _build_content_header(self) -> str:
        """Header at the top of the content pane — kind label and count only.

        Deliberately does NOT include a global 'harnesses: …' chip line —
        that was the V3 mistake; harness state lives in the grid columns.
        Scope toggle is a sibling widget (ScopeToggle), not Rich markup.
        """
        if self._kind == "pi-extension":
            kind_label = "Pi Ext"
        else:
            kind_label = self._kind.replace("-", " ").title()
        n = sum(1 for r in self.state.rows if r.kind == self._kind)
        return f"  [b]{kind_label}[/]   [dim]·[/]   {n} items"
```

- [ ] **Step 5: Update `action_scope` to repaint the toggle**

Replace:

```python
    def action_scope(self, scope: str) -> None:
        if scope not in ("user", "project") or scope == self._scope:
            return
        self._scope = scope
        self.query_one("#asset-grid", AssetGrid).set_scope(scope)
        self._refresh_content_header()
        self._refresh_status_bar()
```

With:

```python
    def action_scope(self, scope: str) -> None:
        if scope not in ("user", "project") or scope == self._scope:
            return
        self._scope = scope
        self.query_one("#asset-grid", AssetGrid).set_scope(scope)
        try:
            self.query_one("#scope-toggle", ScopeToggle).set_active(scope)
        except Exception:
            pass
        self._refresh_content_header()
        self._refresh_status_bar()
```

Leave `action_scope_toggle` and the `s` Binding untouched — they delegate into `action_scope` and therefore pick up the new repaint automatically.

- [ ] **Step 6: Add CSS for the content-header row**

Append to `src/agent_toolkit_tui/css/app.tcss` (just after the rules added in Task 3):

```css

#content-header-row {
    height: auto;
    width: 100%;
    layout: horizontal;
    align: left middle;
}

#content-header-row #content-header {
    width: 1fr;
}
```

- [ ] **Step 7: Run the existing TUI test suite to spot collateral damage**

Run: `uv run pytest tests/test_tui/test_app.py -v`
Expected: most tests pass. `test_content_header_markup_contains_click_actions` and `test_scope_chip_click_switches_scope` may fail — those are updated in Task 5.

- [ ] **Step 8: Commit**

```bash
git add src/agent_toolkit_tui/app.py src/agent_toolkit_tui/css/app.tcss
git commit -m "feat(#99): wire ScopeToggle into TUIApp; drop chips from header"
```

---

## Task 5: Update / replace existing app-level scope tests

**Files:**
- Modify: `tests/test_tui/test_app.py`

- [ ] **Step 1: Read the current tests (lines ~677-727)**

Run: `sed -n '675,730p' tests/test_tui/test_app.py`
Confirm the two tests (`test_scope_chip_click_switches_scope` and `test_content_header_markup_contains_click_actions`) are present and unchanged from the spec excerpt.

- [ ] **Step 2: Replace `test_content_header_markup_contains_click_actions`**

The old test asserted the markup string contained `@click=…` directives — those no longer exist (clicks are widget-level now). Replace the function body with a regression that confirms the markup is plain text (no click directives leaked back in):

Find:

```python
async def test_content_header_markup_contains_click_actions():
    """Regression for #59: the content-header markup wires both chips
    to action_scope via Rich [@click=...] spans, so a mouse click on the
    chip text dispatches the same action u / p do.

    Asserts the *rendered markup* contains the click directives. This is
    what makes the chips actually clickable in the running TUI; without
    these directives the visual chip is just dead text.
    """
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        # _build_content_header is what update() is called with; assert the
        # raw markup string contains both click directives.
        markup = app._build_content_header()
        assert "@click=app.action_scope('project')" in markup, markup
        assert "@click=app.action_scope('user')" in markup, markup
```

Replace with:

```python
async def test_content_header_markup_is_kind_and_count_only():
    """Regression for #99: scope chips moved out of the Static markup into a
    sibling ScopeToggle widget. The content-header markup is now just the
    kind label + item count — no Rich [@click=...] action links.
    """
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        markup = app._build_content_header()
        assert "@click" not in markup, markup
        assert "[dim]" not in markup or markup.count("[dim]") <= 1, markup
        # The kind label and count must still be present.
        assert "items" in markup
```

- [ ] **Step 3: Replace `test_scope_chip_click_switches_scope` with a real mouse-click test**

Find:

```python
async def test_scope_chip_click_switches_scope():
    """Regression for #59: clicking the inactive scope chip flips _scope.

    The chips render as Rich-markup spans inside #content-header. Wrapping
    each chip in [@click=app.action_scope(...)] makes the span a click target.
    Verifies via pilot.click('#content-header'); we don't pin the exact x-
    offset (rich-text regions are layout-sensitive) — instead we assert that
    invoking the click handler via the action route does what u/p does.
    """
    from agent_toolkit_tui.widgets import AssetGrid

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        assert app._scope == "project"
        assert grid._scope == "project"

        # The action wired to the chip's [@click=...] markup. Calling it
        # directly proves the dispatch path the click span will use.
        await app.run_action("scope('user')")
        await pilot.pause()
        assert app._scope == "user"
        assert grid._scope == "user"

        # And back — clicking the (now-inactive) project chip flips it back.
        await app.run_action("scope('project')")
        await pilot.pause()
        assert app._scope == "project"
        assert grid._scope == "project"
```

Replace with:

```python
async def test_scope_toggle_click_switches_scope():
    """Regression for #99: clicking the inactive scope label flips _scope.

    Previously the chips were Rich-markup spans with [@click=...] action
    links; in practice these did not receive mouse clicks reliably. Now
    each scope is a Label widget inside ScopeToggle with an explicit
    on_click handler — verified here by pilot.click on the label id.
    """
    from agent_toolkit_tui.widgets import AssetGrid

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        assert app._scope == "project"
        assert grid._scope == "project"

        # Mouse-click the inactive (user) label. This exercises the real
        # hit-test path, not just the action dispatch.
        await pilot.click("#scope-toggle-user")
        await pilot.pause()
        assert app._scope == "user"
        assert grid._scope == "user"

        # Click the (now-inactive) project label to flip back.
        await pilot.click("#scope-toggle-project")
        await pilot.pause()
        assert app._scope == "project"
        assert grid._scope == "project"


async def test_scope_keyboard_toggle_still_works():
    """Regression for #99: the 's' keybinding still toggles scope after the
    chips were replaced by the ScopeToggle widget. Keyboard path is unchanged.
    """
    from agent_toolkit_tui.widgets import AssetGrid

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        assert app._scope == "project"
        await pilot.press("s")
        await pilot.pause()
        assert app._scope == "user"
        await pilot.press("s")
        await pilot.pause()
        assert app._scope == "project"
```

- [ ] **Step 4: Run the full TUI test module**

Run: `uv run pytest tests/test_tui/test_app.py tests/test_tui/test_scope_toggle.py -v`
Expected: all green. Two old tests have been renamed/replaced; two new tests added.

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui/test_app.py
git commit -m "test(#99): replace scope-chip click tests with real pilot.click coverage"
```

---

## Task 6: Run the full test suite + lint

**Files:** none

- [ ] **Step 1: Run all tests in the worktree**

Run: `uv run pytest -q`
Expected: all green. Pre-existing failures unrelated to this change are out of scope; document them in `flow.log` and surface in the self-review pass if encountered.

- [ ] **Step 2: Run the linter (if configured)**

Run: `uv run ruff check src/agent_toolkit_tui tests/test_tui` (or whatever the project's `lint` script is, per `.github/workflows/ci.yml`).
Expected: no errors. Fix anything that came in with the new code.

- [ ] **Step 3: No commit needed** unless lint/test fixes produced edits. If so:

```bash
git add -A
git commit -m "chore(#99): fix lint/test fallout from scope-toggle rewrite"
```

---

## Self-Review (run at end of plan execution)

1. **Spec coverage:**
   - DoD 1 (paired styling, no dim/underline) → Task 3 CSS + Task 4 `_build_content_header` rewrite.
   - DoD 2 (mouse click flips scope) → Task 2 widget + Task 5 `pilot.click` test.
   - DoD 3 (keyboard `s` still works) → Task 5 `test_scope_keyboard_toggle_still_works`.
   - DoD 4 (no surprises to other header chips) → Task 4 narrows `_build_content_header` to kind + count only.
   - DoD 5 (CI green, self-review PASS) → enforced by flow Steps 8–10.

2. **Placeholder scan:** no TBDs, no "implement appropriate error handling," no "TODO" — every edit has the exact code block.

3. **Type consistency:** `ScopeToggle.set_active(scope: str)` and `ScopeToggle(active="project")` types match across Task 2 (definition), Task 4 (instantiation), and Task 5 (tests). The widget id format `<toggle_id>-<scope>` is consistent across Task 2 (compose), Task 2 (on_click parsing), and Task 5 (`#scope-toggle-user`).

4. **Naming check:** no new method is named `_render_*` — per memory `feedback_textual_render_methods`, that pattern collides with Textual internals. The closest method, `set_active`, follows the existing `KindsSidebar.set_active` convention.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-19-scope-toggle-paired-styling-mouse-click.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — Fresh subagent per task, validator review between tasks, fast iteration. Best fit for this 6-task plan because each task has a clean test gate.
2. **Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
