# TUI Visual Refresh v2 — Navigator layout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the V3 Dashboard layout with the V1 Navigator layout (sidebar `OptionList` drives a swappable content pane). Drop the global "harnesses:" chips, default theme to gruvbox, and surface the package version in the Header subtitle.

**Architecture:** Internal-only refactor of `src/agent_toolkit_tui/app.py`, its CSS, and `widgets/`. The data-model layer (`runner.py`, `state.py`, `messages.py`) and `AssetGrid`'s public API are untouched. The dead `KindsTabs` widget (and its tests) is replaced by a new `KindsSidebar` widget. Headless-mode (`--headless`) byte-for-byte unchanged.

**Tech Stack:** Python 3.13, Textual 8.2.5, pytest with `asyncio_mode = "auto"`, `uv` for env management. Tests use Textual's Pilot API + a `FakeRunner`. Package distribution name is `agent-toolkit`; `importlib.metadata.version("agent-toolkit")` resolves the version.

---

## File Structure

| File | Disposition | Responsibility |
|---|---|---|
| `src/agent_toolkit_tui/widgets/kinds_sidebar.py` | **Create** | New `KindsSidebar` (`Vertical` containing `Static "KINDS"` rail-header + `OptionList`). Posts `KindChanged`. |
| `src/agent_toolkit_tui/widgets/kinds_tabs.py` | **Delete** | Dead — V3-era widget. |
| `src/agent_toolkit_tui/widgets/__init__.py` | **Modify** | Replace `KindsTabs` export with `KindsSidebar`. |
| `src/agent_toolkit_tui/widgets/asset_grid.py` | **Untouched** | Public API and behaviour unchanged. |
| `src/agent_toolkit_tui/app.py` | **Modify** | New layout: `Header` → `Horizontal(sidebar + content)` → `status-bar` → `footer-pending` → `Footer`. Drop "harnesses:" from breadcrumb. Default theme `gruvbox`. Set `SUB_TITLE` to `v<version>`. Wire `OptionList.OptionSelected` event for sidebar. |
| `src/agent_toolkit_tui/css/app.tcss` | **Rewrite** | New Navigator styling: 2-column horizontal main, sidebar styling, content-pane padding, scope chips inside content header. |
| `src/agent_toolkit_tui/__init__.py` | **Modify** | Add `__version__` constant resolved via `importlib.metadata`. |
| `tests/test_tui/test_kinds_tabs.py` | **Delete** | Replaced by `test_kinds_sidebar.py`. |
| `tests/test_tui/test_kinds_sidebar.py` | **Create** | Unit tests for the new widget (`update_state`, `set_active`, `KindChanged` posting, OptionList sync). |
| `tests/test_tui/test_app.py` | **Modify** | Update existing `KindsTabs`-coupled tests to use `KindsSidebar`; add tests for version-in-subtitle, gruvbox-on-mount, and "no harness chips in breadcrumb" regression. |

---

## Task 1: Add `__version__` resolver to package

**Files:**
- Modify: `src/agent_toolkit_tui/__init__.py`

- [ ] **Step 1: Write the failing test**

Create the test file directly (it's a one-shot import smoke test — no existing test file is appropriate):

```python
# tests/test_tui/test_version.py
"""Version resolver — uses importlib.metadata, falls back to 'unknown'."""
from __future__ import annotations


def test_version_is_a_string() -> None:
    from agent_toolkit_tui import __version__
    assert isinstance(__version__, str)
    assert __version__   # not empty


def test_version_matches_pyproject_when_installed() -> None:
    """When the package is installed (uv sync), __version__ should match pyproject."""
    import re
    from pathlib import Path

    from agent_toolkit_tui import __version__

    # Read pyproject from the repo root (test file is at tests/test_tui/test_version.py)
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    text = pyproject.read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    assert m, "version not found in pyproject.toml"
    expected = m.group(1)
    # Either we resolved it correctly, or we're in a non-installed dev shell
    # (in which case __version__ is "unknown"). Both are acceptable in tests
    # because uv sync installs us.
    assert __version__ in (expected, "unknown")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_version.py -v`
Expected: FAIL with `ImportError: cannot import name '__version__' from 'agent_toolkit_tui'`.

- [ ] **Step 3: Write minimal implementation**

Replace `src/agent_toolkit_tui/__init__.py` with:

```python
"""agent-toolkit-tui — Textual cockpit for the agent-toolkit CLI.

Sister to bin/agent-toolkit. Read side imports agent_toolkit_cli; write side shells
out to the bash CLI. Never touches the filesystem directly.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__: str = _pkg_version("agent-toolkit")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["__version__"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_version.py -v`
Expected: PASS — both tests green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/__init__.py tests/test_tui/test_version.py
git commit -m "feat(tui): expose __version__ via importlib.metadata (#43)"
```

---

## Task 2: Create `KindsSidebar` widget (replaces `KindsTabs`)

**Files:**
- Create: `src/agent_toolkit_tui/widgets/kinds_sidebar.py`
- Create: `tests/test_tui/test_kinds_sidebar.py`

The new widget's external contract mirrors `KindsTabs`:
- Public API: `__init__(state, *, id=None)`, `set_active(kind)`, `update_state(state)`
- Posts `KindChanged` when the active kind changes
- Exports `KINDS` and `KIND_LABELS` constants (other tests may import them)

Internally it's an `OptionList` inside a `Vertical` with a `Static` "KINDS" rail-header. Selecting an option fires `set_active` (which posts `KindChanged`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tui/test_kinds_sidebar.py
"""KindsSidebar widget — vertical OptionList with kind counts."""
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import OptionList

from agent_toolkit_tui.messages import KindChanged
from agent_toolkit_tui.state import AssetRow, InventoryState
from agent_toolkit_tui.widgets.kinds_sidebar import (
    KIND_LABELS,
    KINDS,
    KindsSidebar,
)


def _row(kind: str, slug: str) -> AssetRow:
    return AssetRow(
        slug=slug,
        kind=kind,
        origin="first-party",
        description="",
        path=Path("/x"),
        declared_harnesses=("claude",),
        cells={},
    )


def _state(*kinds: str) -> InventoryState:
    return InventoryState(
        toolkit_root=Path("/repo"),
        rows=tuple(_row(k, f"{k}-{i}") for i, k in enumerate(kinds)),
        all_harnesses=("claude", "codex"),
    )


class _Host(App):
    def __init__(self, state: InventoryState) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        yield KindsSidebar(self._state)


def test_counts_each_kind() -> None:
    state = _state("skill", "skill", "agent", "command", "command", "command")
    sidebar = KindsSidebar(state)
    assert sidebar._counts == {
        "skill": 2, "agent": 1, "command": 3,
        "hook": 0, "plugin": 0, "pi-extension": 0,
    }


def test_set_active_noop_for_same_kind() -> None:
    state = _state("skill")
    sidebar = KindsSidebar(state)
    sidebar._active = "skill"
    sidebar.set_active("skill")
    assert sidebar._active == "skill"


def test_set_active_ignores_unknown_kind() -> None:
    state = _state("skill")
    sidebar = KindsSidebar(state)
    sidebar.set_active("nonsense")
    assert sidebar._active == "skill"


def test_kinds_constants_match_labels() -> None:
    assert set(KIND_LABELS.keys()) == set(KINDS)


async def test_set_active_changes_active_when_mounted() -> None:
    """set_active swaps the highlighted option after mount."""
    app = _Host(_state("skill", "agent", "command"))
    async with app.run_test() as pilot:
        sidebar = app.query_one(KindsSidebar)
        sidebar.set_active("agent")
        await pilot.pause()
        assert sidebar._active == "agent"


async def test_update_state_refreshes_counts_preserves_active() -> None:
    """update_state with new state refreshes counts; active option preserved."""
    app = _Host(_state("skill"))
    async with app.run_test() as pilot:
        sidebar = app.query_one(KindsSidebar)
        sidebar.set_active("agent")
        new = _state("skill", "skill", "skill", "agent", "agent")
        sidebar.update_state(new)
        await pilot.pause()
        assert sidebar._counts["skill"] == 3
        assert sidebar._counts["agent"] == 2
        assert sidebar._active == "agent"


async def test_optionlist_selection_posts_kind_changed() -> None:
    """Selecting an option in the OptionList posts KindChanged on the bus."""
    app = _Host(_state("skill", "agent"))
    async with app.run_test() as pilot:
        sidebar = app.query_one(KindsSidebar)
        olist = sidebar.query_one(OptionList)

        received: list[str] = []

        def _capture(event: KindChanged) -> None:
            received.append(event.kind)

        # Subscribe via simple event handler on the host
        app._capture = _capture  # type: ignore[attr-defined]

        # Emulate selection: highlight then "select" (Enter on OptionList)
        olist.focus()
        await pilot.pause()
        # The 2nd option corresponds to "agent" (KINDS index 1)
        olist.highlighted = 1
        await pilot.press("enter")
        await pilot.pause()

        assert sidebar._active == "agent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_kinds_sidebar.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_toolkit_tui.widgets.kinds_sidebar'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/agent_toolkit_tui/widgets/kinds_sidebar.py`:

```python
"""Left-side OptionList that drives the content pane (V1 Navigator).

Posts KindChanged when the user selects a different kind.

Public API mirrors the dead KindsTabs widget so app.py only needs to swap
the import:
- __init__(state, *, id=None)
- set_active(kind) — change selection programmatically
- update_state(state) — re-render counts after a refresh
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from agent_toolkit_tui.messages import KindChanged
from agent_toolkit_tui.state import InventoryState

KINDS: tuple[str, ...] = (
    "skill", "agent", "command", "hook", "plugin", "pi-extension",
)
KIND_LABELS: dict[str, str] = {
    "skill": "Skills",
    "agent": "Agents",
    "command": "Commands",
    "hook": "Hooks",
    "plugin": "Plugins",
    "pi-extension": "Pi Ext",
}


class KindsSidebar(Vertical):
    """Vertical KINDS rail — Static header + OptionList of kinds with counts."""

    def __init__(self, state: InventoryState, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._state = state
        self._counts = self._count(state)
        self._active = "skill"

    @staticmethod
    def _count(state: InventoryState) -> dict[str, int]:
        out = {k: 0 for k in KINDS}
        for r in state.rows:
            if r.kind in out:
                out[r.kind] += 1
        return out

    def compose(self) -> ComposeResult:
        yield Static("KINDS", classes="rail-header")
        yield OptionList(*self._build_options(), id="kinds-list")

    def _build_options(self) -> list[Option]:
        opts: list[Option] = []
        for k in KINDS:
            label = KIND_LABELS[k]
            count = self._counts[k]
            opts.append(Option(f" {label:<10} {count:>3}", id=k))
        return opts

    def on_mount(self) -> None:
        try:
            olist = self.query_one("#kinds-list", OptionList)
            olist.highlighted = KINDS.index(self._active)
        except Exception:
            pass

    def set_active(self, kind: str) -> None:
        """Change selection programmatically. Posts KindChanged if it changes."""
        if kind == self._active or kind not in KINDS:
            return
        self._active = kind
        try:
            olist = self.query_one("#kinds-list", OptionList)
            olist.highlighted = KINDS.index(kind)
        except Exception:
            pass
        self.post_message(KindChanged(kind=kind))

    def update_state(self, state: InventoryState) -> None:
        """Re-render counts after a refresh. Does not change active option."""
        self._state = state
        self._counts = self._count(state)
        try:
            olist = self.query_one("#kinds-list", OptionList)
            olist.clear_options()
            olist.add_options(self._build_options())
            olist.highlighted = KINDS.index(self._active)
        except Exception:
            pass

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """User pressed Enter on an option — switch active kind."""
        if event.option.id and event.option.id in KINDS:
            self.set_active(event.option.id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_kinds_sidebar.py -v`
Expected: PASS — all 7 tests green.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/kinds_sidebar.py tests/test_tui/test_kinds_sidebar.py
git commit -m "feat(tui): add KindsSidebar widget (V1 Navigator) (#43)"
```

---

## Task 3: Wire `KindsSidebar` into the app and delete `KindsTabs`

This task swaps the widget in `app.py`, deletes the old widget + its tests, drops the global "harnesses:" chips from the breadcrumb, defaults the theme to gruvbox, and shows the version as `SUB_TITLE`.

**Files:**
- Modify: `src/agent_toolkit_tui/app.py` (full layout rewrite of `compose()` + `on_mount()` + breadcrumb)
- Modify: `src/agent_toolkit_tui/widgets/__init__.py`
- Delete: `src/agent_toolkit_tui/widgets/kinds_tabs.py`
- Delete: `tests/test_tui/test_kinds_tabs.py`
- Modify: `tests/test_tui/test_app.py` (rename `KindsTabs` → `KindsSidebar`, drop the harness-chip assertion in `test_breadcrumb_*`)

- [ ] **Step 1: Write the failing tests**

Update `tests/test_tui/test_app.py`. Apply these edits:

**1a. Replace the `KindsTabs` import and usage in `test_number_key_switches_kind`:**

```python
# BEFORE
async def test_number_key_switches_kind():
    """Pressing 1-6 changes the active kind in both AssetGrid and KindsTabs."""
    from agent_toolkit_tui.widgets import AssetGrid, KindsTabs

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        tabs = app.query_one("#kinds-tabs", KindsTabs)
        assert grid._kind == "skill"
        assert tabs._active == "skill"

        await pilot.press("2")  # agents
        await pilot.pause()
        assert grid._kind == "agent"
        assert tabs._active == "agent"

        await pilot.press("3")  # commands
        await pilot.pause()
        assert grid._kind == "command"
        assert tabs._active == "command"
```

becomes

```python
async def test_number_key_switches_kind():
    """Pressing 1-6 changes the active kind in AssetGrid and KindsSidebar."""
    from agent_toolkit_tui.widgets import AssetGrid, KindsSidebar

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        sidebar = app.query_one("#kinds-sidebar", KindsSidebar)
        assert grid._kind == "skill"
        assert sidebar._active == "skill"

        await pilot.press("2")  # agents
        await pilot.pause()
        assert grid._kind == "agent"
        assert sidebar._active == "agent"

        await pilot.press("3")  # commands
        await pilot.pause()
        assert grid._kind == "command"
        assert sidebar._active == "command"
```

**1b. Replace the breadcrumb assertion to drop the "harnesses:" expectation and assert harness chips are gone:**

```python
# BEFORE
async def test_breadcrumb_reflects_current_kind_and_scope():
    """The breadcrumb Static updates when kind or scope changes."""
    from textual.widgets import Static

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        breadcrumb = app.query_one("#breadcrumb", Static)
        text = str(breadcrumb.render())
        assert "Skill" in text
        assert "project" in text

        await pilot.press("2")  # agent
        await pilot.press("u")  # user scope
        await pilot.pause()
        text = str(app.query_one("#breadcrumb", Static).render())
        assert "Agent" in text
        assert "user" in text
```

becomes

```python
async def test_breadcrumb_reflects_current_kind_and_scope():
    """The content header (formerly 'breadcrumb') shows kind + scope only."""
    from textual.widgets import Static

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.query_one("#content-header", Static)
        text = str(header.render())
        assert "Skill" in text
        assert "project" in text
        # Regression: V1 Navigator must NOT show global "harnesses:" chips.
        assert "harnesses" not in text.lower()

        await pilot.press("2")  # agent
        await pilot.press("u")  # user scope
        await pilot.pause()
        text = str(app.query_one("#content-header", Static).render())
        assert "Agent" in text
        assert "user" in text
        assert "harnesses" not in text.lower()
```

**1c. Append three new tests (at end of file):**

```python
# ── V1 Navigator: theme + version + no harness chips ──────────────────────

async def test_default_theme_is_gruvbox():
    """on_mount sets self.theme = 'gruvbox' (matches claude_tui_tools)."""
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "gruvbox"


async def test_subtitle_shows_version():
    """Header subtitle exposes the package version, e.g. 'v0.3.0' or 'vunknown'."""
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        sub = app.sub_title
        # Either "v<X.Y.Z>" if installed, or "vunknown" in a non-installed dev shell.
        assert sub.startswith("v"), f"sub_title should start with 'v', got {sub!r}"
        assert len(sub) >= 2, "sub_title should include some version text"


async def test_no_harness_chips_anywhere_outside_grid():
    """Regression for #43 reopen — no global 'harnesses: claude codex …' chip row."""
    from textual.widgets import Static

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Walk every Static and assert none of them render a "harnesses:" chip line.
        for static in app.query(Static):
            text = str(static.render()).lower()
            assert "harnesses:" not in text, (
                f"unexpected 'harnesses:' chip line in #{static.id}: {text!r}"
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_app.py -v`
Expected:
- `test_number_key_switches_kind` → FAIL on `from agent_toolkit_tui.widgets import KindsSidebar` (or on the `#kinds-sidebar` query) because we haven't wired the new widget yet.
- `test_breadcrumb_reflects_current_kind_and_scope` → FAIL because `#content-header` doesn't exist yet (it's still `#breadcrumb`).
- `test_default_theme_is_gruvbox` → FAIL because current theme is `tokyo-night`.
- `test_subtitle_shows_version` → FAIL because `sub_title` is empty.
- `test_no_harness_chips_anywhere_outside_grid` → FAIL because the V3 breadcrumb still emits "harnesses: …".

- [ ] **Step 3: Write the implementation**

Replace `src/agent_toolkit_tui/widgets/__init__.py` with:

```python
"""Textual widgets for agent-toolkit-tui."""

from agent_toolkit_tui.widgets.asset_grid import AssetGrid
from agent_toolkit_tui.widgets.kinds_sidebar import KindsSidebar

__all__ = ["AssetGrid", "KindsSidebar"]
```

Delete the old widget and its tests:

```bash
rm src/agent_toolkit_tui/widgets/kinds_tabs.py
rm tests/test_tui/test_kinds_tabs.py
```

Now rewrite `src/agent_toolkit_tui/app.py`. Replace the file contents with:

```python
"""The Textual App + main() entry point.

Owns the runner, the state, and the Apply path. Widgets only render and emit
messages; they don't know about the runner.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from agent_toolkit_tui import __version__
from agent_toolkit_tui.messages import (
    AssetToggled,
    KindChanged,
    ScopeChanged,
)
from agent_toolkit_tui.runner import CLIRunner, PlanResult, RunnerError
from agent_toolkit_tui.state import InventoryState, build_state
from agent_toolkit_tui.widgets import AssetGrid, KindsSidebar


class ConfirmDiscardScreen(ModalScreen[bool]):
    """Yes/No prompt shown when quitting with unapplied pending edits."""

    DEFAULT_CSS = """
    ConfirmDiscardScreen {
        align: center middle;
    }
    ConfirmDiscardScreen > Vertical {
        background: $panel;
        border: thick $warning;
        padding: 1 2;
        width: 50;
        height: auto;
    }
    ConfirmDiscardScreen Label {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    ConfirmDiscardScreen #buttons {
        layout: horizontal;
        height: auto;
        align: center middle;
    }
    ConfirmDiscardScreen Button {
        margin: 0 2;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "discard", "Discard"),
        Binding("n", "cancel", "Cancel"),
    ]

    def __init__(self, n_pending: int) -> None:
        super().__init__()
        self._n_pending = n_pending

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Discard {self._n_pending} pending change(s)?")
            with Horizontal(id="buttons"):
                yield Button("Discard", variant="warning", id="discard")
                yield Button("Cancel", variant="primary", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "discard")

    def action_discard(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class TUIApp(App):
    """agent-toolkit-tui — Textual cockpit over bin/agent-toolkit."""

    CSS_PATH = "css/app.tcss"
    TITLE = "agent-toolkit-tui"

    BINDINGS = [
        Binding("ctrl+s", "apply", "Apply", priority=True),
        Binding("ctrl+d", "diff", "Diff", priority=True),
        Binding("ctrl+r", "refresh", "Refresh", priority=True),
        Binding("ctrl+z", "revert", "Revert", priority=True),
        Binding("slash", "focus_filter", "Filter", priority=True),
        Binding("u", "scope('user')", "user scope"),
        Binding("p", "scope('project')", "project scope"),
        Binding("1", "kind('skill')", "Skills", show=False),
        Binding("2", "kind('agent')", "Agents", show=False),
        Binding("3", "kind('command')", "Commands", show=False),
        Binding("4", "kind('hook')", "Hooks", show=False),
        Binding("5", "kind('plugin')", "Plugins", show=False),
        Binding("6", "kind('pi-extension')", "Pi Ext", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, toolkit_root: Path, runner: CLIRunner | None = None) -> None:
        super().__init__()
        self.toolkit_root = toolkit_root
        self.runner = runner or CLIRunner(toolkit_root=toolkit_root)
        self.state: InventoryState = build_state(self.runner)
        self._scope: str = "project"
        self._kind: str = "skill"
        self.sub_title = f"v{__version__}"

    # ----- composition ----------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield KindsSidebar(self.state, id="kinds-sidebar")
            with Vertical(id="content"):
                yield Static(self._build_content_header(), id="content-header")
                yield AssetGrid(self.state, id="asset-grid")
        yield Static("", id="status-bar")
        yield Static("", id="footer-pending")
        yield Footer()

    # ----- lifecycle ------------------------------------------------------
    def on_mount(self) -> None:
        try:
            self.theme = "gruvbox"
        except Exception:
            pass
        self._refresh_pending_label()
        self._refresh_status_bar()
        # Default focus on the data table, not the filter Input — `q` and other
        # bindings should fire as bindings, not as text input.
        try:
            self.query_one("#grid-table", DataTable).focus()
        except Exception:
            pass

    # ----- message handlers ------------------------------------------------
    def on_kind_changed(self, event: KindChanged) -> None:
        self._kind = event.kind
        self.query_one("#asset-grid", AssetGrid).set_kind(event.kind)
        self._refresh_content_header()
        self._refresh_status_bar()

    def on_scope_changed(self, event: ScopeChanged) -> None:
        self._scope = event.scope
        self.query_one("#asset-grid", AssetGrid).set_scope(event.scope)
        self._refresh_content_header()
        self._refresh_status_bar()

    def on_asset_toggled(self, event: AssetToggled) -> None:
        self._refresh_pending_label()
        self._refresh_status_bar()

    # ----- actions --------------------------------------------------------
    def action_quit(self) -> None:
        grid = self.query_one("#asset-grid", AssetGrid)
        n = len(grid.pending_entries())
        if n == 0:
            self.exit()
            return

        def _on_close(discard: bool | None) -> None:
            if discard:
                self.exit()

        self.push_screen(ConfirmDiscardScreen(n), _on_close)

    def action_focus_filter(self) -> None:
        try:
            self.query_one("#grid-filter", Input).focus()
        except Exception:
            pass

    def action_scope(self, scope: str) -> None:
        if scope not in ("user", "project") or scope == self._scope:
            return
        self._scope = scope
        self.query_one("#asset-grid", AssetGrid).set_scope(scope)
        self._refresh_content_header()
        self._refresh_status_bar()

    def action_kind(self, kind: str) -> None:
        if kind == self._kind:
            return
        self._kind = kind
        self.query_one("#kinds-sidebar", KindsSidebar).set_active(kind)
        self.query_one("#asset-grid", AssetGrid).set_kind(kind)
        self._refresh_content_header()
        self._refresh_status_bar()

    def action_refresh(self) -> None:
        self.state = build_state(self.runner)
        self.query_one("#asset-grid", AssetGrid).update_state(self.state)
        self.query_one("#kinds-sidebar", KindsSidebar).update_state(self.state)
        self._refresh_pending_label()
        self._refresh_content_header()
        self._refresh_status_bar()

    def action_revert(self) -> None:
        grid = self.query_one("#asset-grid", AssetGrid)
        n = len(grid.pending_entries())
        grid.clear_pending()
        self._refresh_pending_label()
        self._refresh_status_bar()
        self.query_one("#footer-pending", Static).update(
            f"reverted: {n} pending cleared"
        )

    def action_diff(self) -> None:
        # Diff = run pending through --dry-run and surface counts in the footer.
        grid = self.query_one("#asset-grid", AssetGrid)
        results = self._apply_pending(dry_run=True, grid=grid)
        ok = sum(r.ok for r in results)
        failed = sum(r.failed for r in results)
        self.query_one("#footer-pending", Static).update(
            f"diff: {ok} would-link, {failed} errors"
        )

    def action_apply(self) -> None:
        grid = self.query_one("#asset-grid", AssetGrid)
        results = self._apply_pending(dry_run=False, grid=grid)
        # Refresh state after apply (per spec: always reconcile)
        self.state = build_state(self.runner)
        grid.update_state(self.state)
        ok = sum(r.ok for r in results)
        failed = sum(r.failed for r in results)
        if failed == 0:
            grid.clear_pending()
        self._refresh_pending_label()
        self._refresh_status_bar()
        self.query_one("#footer-pending", Static).update(
            f"applied: {ok} ok, {failed} failed"
        )

    # ----- internals ------------------------------------------------------
    def _apply_pending(self, *, dry_run: bool, grid: AssetGrid) -> list[PlanResult]:
        """Walk the pending queue, batch by (scope, harness, op), call runner once per batch."""
        pending = grid.pending_entries()
        # batches: (scope, harness, op) -> [(kind, slug), ...]
        batches: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
        for (scope, harness, kind, slug), op in pending.items():
            batches[(scope, harness, op)].append((kind, slug))

        results: list[PlanResult] = []
        for (scope, harness, op), entries in sorted(batches.items()):
            try:
                if op == "link":
                    res = self.runner.link_plan(
                        scope=scope, harness=harness,
                        entries=entries, dry_run=dry_run,
                    )
                else:
                    res = self.runner.unlink_plan(
                        scope=scope, harness=harness,
                        entries=entries, dry_run=dry_run,
                    )
                results.append(res)
            except RunnerError as e:
                # Programmer bug — log to footer, leave queue untouched
                self.query_one("#footer-pending", Static).update(f"error: {e}")
                break
        return results

    def _refresh_pending_label(self) -> None:
        n = len(self.query_one("#asset-grid", AssetGrid).pending_entries())
        self.query_one("#footer-pending", Static).update(f"Pending: {n}")

    # ----- content header + status bar ------------------------------------
    def _build_content_header(self) -> str:
        """Header at the top of the content pane — kind label, count, scope chips.

        Deliberately does NOT include a global 'harnesses: …' chip line —
        that was the V3 mistake; harness state lives in the grid columns.
        """
        if self._kind == "pi-extension":
            kind_label = "Pi Ext"
        else:
            kind_label = self._kind.replace("-", " ").title()
        n = sum(1 for r in self.state.rows if r.kind == self._kind)
        # Scope chips: highlight the active one with [reverse], dim the other.
        chips = []
        for s in ("project", "user"):
            if s == self._scope:
                chips.append(f"[reverse] {s} [/]")
            else:
                chips.append(f" [dim]{s}[/] ")
        return (
            f"  [b]{kind_label}[/]   [dim]·[/]   {n} items   "
            f"[dim]·[/]   scope: {' '.join(chips)}"
        )

    def _refresh_content_header(self) -> None:
        try:
            self.query_one("#content-header", Static).update(
                self._build_content_header()
            )
        except Exception:
            pass

    def _refresh_status_bar(self) -> None:
        """Roll up state into linked / pending / drifted / broken counts."""
        linked = drifted = broken = 0
        for row in self.state.rows:
            for cell in row.cells.values():
                if cell.status in ("linked", "linked-matches"):
                    linked += 1
                elif cell.status == "linked-drifted":
                    drifted += 1
                elif cell.status == "broken":
                    broken += 1
        try:
            grid = self.query_one("#asset-grid", AssetGrid)
            pending = len(grid.pending_entries())
        except Exception:
            pending = 0
        text = (
            f"  [b green]{linked}[/] linked   "
            f"[b yellow]{pending}[/] pending   "
            f"[b orange3]{drifted}[/] drifted   "
            f"[b red]{broken}[/] broken"
        )
        try:
            self.query_one("#status-bar", Static).update(text)
        except Exception:
            pass


# --------------------------------------------------------------------------
# Entry point — both the interactive TUI and the --headless mode used by
# Layer-3 bats smoke tests live here.
# --------------------------------------------------------------------------

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="agent-toolkit-tui",
        description="Textual cockpit for agent-toolkit.",
    )
    p.add_argument("--toolkit-repo", dest="toolkit_repo", type=Path, default=Path.cwd(),
                   help="Path to the agent-toolkit repo (default: current directory).")
    p.add_argument("--headless", action="store_true",
                   help="Don't launch the UI; apply --plan and exit.")
    p.add_argument("--plan", type=Path, default=None,
                   help="With --headless: path to a plan file (kind:slug per line) or '-' for stdin.")
    p.add_argument("--scope", choices=("user", "project"), default="user",
                   help="With --headless: scope to apply the plan under.")
    p.add_argument("--harness", default="claude",
                   help="With --headless: harness to apply the plan to.")
    p.add_argument("--op", choices=("link", "unlink"), default="link",
                   help="With --headless: operation to perform.")
    p.add_argument("--apply", action="store_true",
                   help="With --headless: actually apply (default would dry-run).")
    return p.parse_args(argv)


def _read_plan(path: Path) -> list[tuple[str, str]]:
    if str(path) == "-":
        text = sys.stdin.read()
    else:
        text = path.read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            print(f"malformed plan line: {raw!r}", file=sys.stderr)
            continue
        kind, slug = line.split(":", 1)
        out.append((kind.strip(), slug.strip()))
    return out


def main() -> int:
    args = _parse_args(sys.argv[1:])
    toolkit_root = args.toolkit_repo.resolve()

    if args.headless:
        if args.plan is None:
            print("--headless requires --plan", file=sys.stderr)
            return 2
        runner = CLIRunner(toolkit_root=toolkit_root)
        entries = _read_plan(args.plan)
        if args.op == "link":
            res = runner.link_plan(
                scope=args.scope, harness=args.harness,
                entries=entries, dry_run=not args.apply,
            )
        else:
            res = runner.unlink_plan(
                scope=args.scope, harness=args.harness,
                entries=entries, dry_run=not args.apply,
            )
        verb = "applied" if args.apply else "would apply"
        print(f"{verb}: {res.ok} ok, {res.failed} failed", file=sys.stderr)
        return 0 if res.failed == 0 else 1

    TUIApp(toolkit_root=toolkit_root).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

> **Implementation notes for the reviewer:**
> - The `compose()` switches from a flat vertical stack to `Header → Horizontal(KindsSidebar | Vertical(content-header + AssetGrid)) → status-bar → footer-pending → Footer`. The grid's filter Input stays *inside* `AssetGrid` (its compose already yields it).
> - `_build_breadcrumb` / `_refresh_breadcrumb` are renamed to `_build_content_header` / `_refresh_content_header` and the "harnesses: …" segment is gone.
> - `_harnesses_for_display` and the module-level `HARNESSES_DISPLAY_ORDER` constant are removed — they only existed to render the dropped chip line.
> - `sub_title` is set in `__init__` (Textual reads it before mount).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/ -v`
Expected: ALL tests pass — including the 3 new tests, the modified breadcrumb test, the modified `test_number_key_switches_kind`, and the existing kind/scope/quit/etc tests untouched by this task.

If any pre-existing test fails, debug before committing — don't paper over it.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(tui): swap to V1 Navigator layout, default theme gruvbox (#43)

- Replace KindsTabs (top tab strip) with KindsSidebar (left OptionList)
- Drop global 'harnesses: …' chip line from content header
- Default theme: gruvbox (matches claude_tui_tools)
- Surface package version as Header sub_title (e.g. 'v0.3.0')
- Delete dead kinds_tabs.py + test_kinds_tabs.py"
```

---

## Task 4: Rewrite the CSS for Navigator layout

The CSS rewrite is its own task because (a) it's the visible side of the change, (b) it's easy to verify in isolation, and (c) the file is small enough to land in one go.

**Files:**
- Modify: `src/agent_toolkit_tui/css/app.tcss` (full rewrite)

The grid's `DEFAULT_CSS` inside `widgets/asset_grid.py` already gives `AssetGrid` a `border: round $primary` + `Input#grid-filter` styling. We do **not** modify that — the goal here is the *outer* layout (sidebar / content split / status bar / footer-pending row). Borrowing freely from `/tmp/atui-mockups/1/app.tcss` while keeping the existing IDs the app uses (`#main`, `#kinds-sidebar`, `#kinds-list`, `#content`, `#content-header`, `#status-bar`, `#footer-pending`).

- [ ] **Step 1: Manual verification — launch the TUI before changing CSS**

Run the TUI once against the real repo to confirm it boots with the new layout (Task 3 wired the layout). The styling will look unfinished, but everything should *function* (sidebar visible, navigation works, version in subtitle, gruvbox palette).

```bash
uv run agent-toolkit-tui --toolkit-repo /Users/ajanderson/GitHub/agent-toolkit
# Press q to quit.
```

If the app crashes, fix that first — do not advance to the CSS rewrite.

- [ ] **Step 2: Rewrite `src/agent_toolkit_tui/css/app.tcss`**

Replace the file contents with:

```css
/* agent-toolkit-tui — V1 Navigator, gruvbox-friendly.
   Layout: Header → Horizontal(KindsSidebar | Vertical(content-header + AssetGrid))
           → status-bar → footer-pending → Footer.
*/

Screen {
    background: $surface;
}

/* Main row — sidebar + content side-by-side, full remaining height. */
#main {
    layout: horizontal;
    height: 1fr;
}

/* Left rail. */
#kinds-sidebar {
    width: 24;
    min-width: 20;
    max-width: 30;
    background: $panel;
    border-right: tall $primary-darken-2;
}

#kinds-sidebar .rail-header {
    text-style: bold;
    color: $accent;
    padding: 1 2 1 2;
    background: $panel;
    border-bottom: tall $primary-darken-2;
}

#kinds-list {
    background: $panel;
    border: none;
    padding: 1 0;
    scrollbar-size-vertical: 1;
    scrollbar-background: $panel-darken-1;
    scrollbar-color: $primary-darken-2;
    scrollbar-color-hover: $primary;
}

OptionList > .option-list--option {
    padding: 0 2;
}
OptionList > .option-list--option-highlighted {
    background: $primary;
    color: $text;
    text-style: bold;
}
OptionList > .option-list--option-hover {
    background: $boost;
}

/* Content pane (right side). */
#content {
    width: 1fr;
    background: $surface;
    padding: 1 3;
}

#content-header {
    height: 2;
    color: $text;
    padding: 0 0 1 0;
    border-bottom: tall $primary-darken-2;
    margin: 0 0 1 0;
}

/* AssetGrid lives inside #content; its own DEFAULT_CSS handles border + filter. */
#asset-grid {
    height: 1fr;
}

/* DataTable header + cursor — kept consistent with the V3 styling but
   palette-neutral so gruvbox lights up correctly. */
DataTable > .datatable--header {
    background: $panel;
    color: $accent;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: $primary;
    color: $text;
}

/* Status bar — full-width row above the footer. */
#status-bar {
    height: 1;
    color: $text-muted;
    background: $panel;
    padding: 0 2;
    border-top: tall $primary-darken-2;
}

#footer-pending {
    height: 1;
    color: $accent;
    background: $panel;
    padding: 0 2;
}
```

- [ ] **Step 3: Verify visually + run tests**

Re-launch and eyeball the layout — sidebar styled, content-header rule under the title, no flicker:

```bash
uv run agent-toolkit-tui --toolkit-repo /Users/ajanderson/GitHub/agent-toolkit
# Walk: 1/2/3/4/5/6 to switch kinds, u/p to switch scope, / to filter, q to quit.
```

Then re-run all tests to make sure no styling-rooted regression slipped in (e.g. a widget hidden because of `display: none` from a CSS typo):

Run: `uv run pytest tests/test_tui/ -v`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add src/agent_toolkit_tui/css/app.tcss
git commit -m "style(tui): rewrite CSS for V1 Navigator layout (#43)"
```

---

## Task 5: Capture before/after screenshots (PR artefacts)

The PR's "Definition of Done" requires before/after screenshots. The "before" is `main` (V3 Dashboard, post-#47); the "after" is the current branch tip.

These screenshots are **artefacts**, committed to `assets/verification/43/` (which is gitignored), surfaced in the PR via `superpowers:finishing-a-development-branch`. They are not committed to the branch.

**Files:**
- Create: `assets/verification/43/before.txt` (V3 layout capture from `main`)
- Create: `assets/verification/43/after.txt` (V1 Navigator capture from current branch)
- Append to: `assets/verification/43/flow.log` (log entries)

- [ ] **Step 1: Capture the AFTER state from the worktree**

Use `tmux capture-pane` after launching the TUI in a tmux session. The textual-tui skill describes the workflow.

```bash
# (Inside the worktree)
CC_TMUX="cc-43-after"
tmux new-session -d -s "$CC_TMUX" -x 160 -y 44
tmux send-keys -t "$CC_TMUX" "cd $(pwd) && uv run agent-toolkit-tui --toolkit-repo /Users/ajanderson/GitHub/agent-toolkit" Enter
sleep 4
tmux capture-pane -t "$CC_TMUX" -p > assets/verification/43/after.txt
tmux send-keys -t "$CC_TMUX" "q" Enter
sleep 1
tmux kill-session -t "$CC_TMUX" 2>/dev/null
```

- [ ] **Step 2: Capture the BEFORE state from `main`**

Use a *separate* worktree on `main` so we don't dirty the current branch.

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli
git worktree add .worktrees/before-43 main
cd .worktrees/before-43
uv sync --extra tui

CC_TMUX="cc-43-before"
tmux new-session -d -s "$CC_TMUX" -x 160 -y 44
tmux send-keys -t "$CC_TMUX" "cd $(pwd) && uv run agent-toolkit-tui --toolkit-repo /Users/ajanderson/GitHub/agent-toolkit" Enter
sleep 4
tmux capture-pane -t "$CC_TMUX" -p > /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/feat-43-tui-visual-refresh-v2/assets/verification/43/before.txt
tmux send-keys -t "$CC_TMUX" "q" Enter
sleep 1
tmux kill-session -t "$CC_TMUX" 2>/dev/null

cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli
git worktree remove .worktrees/before-43
cd .worktrees/feat-43-tui-visual-refresh-v2
```

- [ ] **Step 3: Verify the captures**

Run: `wc -l assets/verification/43/before.txt assets/verification/43/after.txt`
Expected: each file has at least 30 non-empty lines (full screen capture).

If `before.txt` is mostly blank, the dev shell on `main` likely didn't have textual installed — re-run `uv sync --extra tui` in `.worktrees/before-43` and retry the capture.

- [ ] **Step 4: Append a log entry**

Append to `assets/verification/43/flow.log`:

```bash
{
  echo ""
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) — Verification artefacts ==="
  echo "before.txt — $(wc -l < assets/verification/43/before.txt) lines"
  echo "after.txt  — $(wc -l < assets/verification/43/after.txt) lines"
} >> assets/verification/43/flow.log
```

- [ ] **Step 5: No commit**

These files live under `assets/verification/` which is gitignored. Do **not** `git add` them. They are referenced from the PR body as artefacts.

If `assets/verification/` is *not* in the `.gitignore`, add the line `assets/verification/` to `.gitignore` and commit just the gitignore change:

```bash
grep -q "^assets/verification/" .gitignore || {
  echo "assets/verification/" >> .gitignore
  git add .gitignore
  git commit -m "chore: gitignore assets/verification/ (#43)"
}
```

---

## Self-review checklist

After all 5 tasks land, the reviewer/agent should walk this list before opening the PR.

| Spec § | Implementation | Where |
|---|---|---|
| R1: Navigator layout (sidebar drives content) | `KindsSidebar` widget + `compose()` `Horizontal` row | Tasks 2 & 3 |
| R1: 1/2/…/6 number-key bindings preserved | `BINDINGS` block in `app.py` unchanged | Task 3 |
| R1: `KindChanged` contract preserved | New widget posts `KindChanged` from `set_active`/`OptionList` event | Task 2 |
| R2: No global "harnesses:" chips | `_build_content_header` returns kind+scope only; regression test | Task 3 (test 1c) |
| R2: Scope chips inside content pane header | `_build_content_header` includes scope chips inline | Task 3 |
| R3: Version visible | `sub_title = f"v{__version__}"` in `TUIApp.__init__` | Task 3 |
| R3: Pulled via `importlib.metadata` with `"unknown"` fallback | `__init__.py` uses `try/except PackageNotFoundError` | Task 1 |
| R4: Default theme = gruvbox | `on_mount` sets `self.theme = "gruvbox"` | Task 3 |
| R4: `t` cycles themes | Textual built-in command-palette theme cycling untouched | (no code; it just works) |
| R5: No data-model changes | `runner.py`, `state.py`, `messages.py` not in any task's "modify" list | (verified by grep before commit) |
| R5: `AssetGrid` public API untouched | `widgets/asset_grid.py` not in any task's "modify" list | (verified by grep before commit) |
| R6: Headless mode untouched | `_parse_args`, `_read_plan`, `--headless` block byte-for-byte preserved in Task 3's `app.py` rewrite | (verified by `git diff --stat` showing identical hunks) |
| DoD #6: Before/after screenshots | `assets/verification/43/{before,after}.txt` | Task 5 |
| DoD #7: Headless regression | `tests/test_tui/test_headless.py` still passes | Task 3 (full pytest) |

**Final manual checks before opening the PR:**

1. Launch the TUI, verify gruvbox palette (warm beige/orange tones), no top "harnesses:" line, sidebar on the left with kinds list.
2. Press `1`, `2`, `3`, … — content pane updates, sidebar highlight follows, breadcrumb (`#content-header`) shows the new kind.
3. Press `u`, `p` — scope chips swap in the header.
4. Press `t` — the theme cycles to the next built-in theme (gruvbox → next on the list).
5. Header bar shows `agent-toolkit-tui` on the left and `v0.3.0` (or `vunknown`) on the right.
6. Press `q` with no pending changes → exits immediately.
7. `uv run agent-toolkit-tui --headless --plan -` reads from stdin and exits with the right code.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-05-tui-visual-refresh-v2.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
