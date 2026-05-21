# TUI Column-Header Info Affordance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a discoverable `ⓘ` glyph + `i`-key info modal to the TUI `SkillGrid` so users can see which agent harnesses are bundled under the **Universal** column without leaving the TUI. The first registration is Universal; the data shape is reusable for other columns later.

**Architecture:** Three small additions to `agent_toolkit_tui`:

1. A `column_info.py` module that defines `ColumnInfo` (title + lines) and a `COLUMN_INFO: dict[str, Callable[[], ColumnInfo]]` registry. The Universal entry pulls its lines from `agent_toolkit_cli.skill_agents.get_universal_agents()` at call time so it can never go stale.
2. A `ColumnInfoModal(ModalScreen)` in `widgets/column_info_modal.py`, modeled after the existing `ConfirmDiscardScreen` in `app.py`. Shows the title + bullet list; `esc` and `i` close.
3. Wiring inside `SkillGrid`:
   - Append `ⓘ` to any column label whose name has an entry in `COLUMN_INFO`.
   - New `i` binding that, when the cursor is on a column with registered info, opens the modal via `app.push_screen(...)`.

**Tech Stack:** Python 3.12+ · Textual ≥ 0.79 · pytest-asyncio Pilot tests · existing `uv` toolchain.

---

## File Structure

| Path | Role |
|---|---|
| Create: `src/agent_toolkit_tui/column_info.py` | `ColumnInfo` dataclass + `COLUMN_INFO` registry + `get_column_info(name)` helper. |
| Create: `src/agent_toolkit_tui/widgets/column_info_modal.py` | `ColumnInfoModal(ModalScreen)` widget. |
| Modify: `src/agent_toolkit_tui/widgets/__init__.py` | Export `ColumnInfoModal`. |
| Modify: `src/agent_toolkit_tui/widgets/skill_grid.py` | Append glyph in `_rebuild`; add `i` binding + `action_open_column_info`. |
| Create: `tests/test_tui/test_column_info.py` | Unit tests for the registry. |
| Create: `tests/test_tui/test_column_info_modal.py` | Pilot test: glyph rendered, `i` opens modal, `esc` closes. |

Files that change together (`column_info.py` + the SkillGrid wiring + the modal) ship in adjacent tasks so a reviewer sees one coherent change per task.

---

## Task 1: ColumnInfo data shape + Universal registration

**Files:**
- Create: `src/agent_toolkit_tui/column_info.py`
- Test: `tests/test_tui/test_column_info.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tui/test_column_info.py`:

```python
"""Tests for the per-column info registry."""
from __future__ import annotations

from agent_toolkit_tui.column_info import (
    COLUMN_INFO,
    ColumnInfo,
    get_column_info,
)


def test_universal_entry_is_registered():
    assert "universal" in COLUMN_INFO


def test_get_column_info_universal_returns_columninfo():
    info = get_column_info("universal")
    assert isinstance(info, ColumnInfo)
    assert info.title.lower().startswith("universal")
    # At least one harness should be listed.
    assert info.lines
    # The description block is the first paragraph above the bullet list.
    assert any(line.startswith("•") or line.startswith("-") or line.strip()
               for line in info.lines)


def test_get_column_info_universal_lists_known_harnesses():
    from agent_toolkit_cli.skill_agents import get_universal_agents
    info = get_column_info("universal")
    text = "\n".join(info.lines)
    for name in get_universal_agents():
        assert name in text, f"universal harness {name!r} missing from info"


def test_get_column_info_unknown_returns_none():
    assert get_column_info("does-not-exist") is None


def test_get_column_info_is_recomputed_each_call():
    """Registry stores a factory, so a later catalog change is reflected."""
    info_a = get_column_info("universal")
    info_b = get_column_info("universal")
    # Distinct objects (factory called twice), but equal content.
    assert info_a is not info_b
    assert info_a.title == info_b.title
    assert info_a.lines == info_b.lines
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "$(git rev-parse --show-toplevel)"
uv run pytest tests/test_tui/test_column_info.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_tui.column_info'`.

- [ ] **Step 3: Implement `column_info.py`**

Create `src/agent_toolkit_tui/column_info.py`:

```python
"""Per-column info content for SkillGrid headers.

A column "info entry" is the content shown when the user presses `i` while
the cursor is on a cell in that column. The registry maps a column name
(matching an entry in INTERACTIVE_AGENTS, plus future extensions like
"slug"/"state") to a factory that produces a fresh ColumnInfo at call time.

Factories — not pre-built ColumnInfo objects — so the Universal list
always reflects the current catalog without an import-time snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agent_toolkit_cli.skill_agents import AGENTS, get_universal_agents


@dataclass(frozen=True)
class ColumnInfo:
    """Content displayed by ColumnInfoModal for one column."""
    title: str
    lines: list[str]


def _universal_info() -> ColumnInfo:
    harness_names = get_universal_agents()
    description = [
        "Toggles link/unlink for every harness whose",
        "skillsDir is `.agents/skills`.",
        "",
        "Included harnesses:",
    ]
    bullets = [
        f"  • {name} — {AGENTS[name].display_name}"
        for name in harness_names
    ]
    return ColumnInfo(
        title="Universal bundle",
        lines=description + bullets,
    )


COLUMN_INFO: dict[str, Callable[[], ColumnInfo]] = {
    "universal": _universal_info,
}


def get_column_info(name: str) -> ColumnInfo | None:
    """Return a fresh ColumnInfo for `name`, or None if unregistered."""
    factory = COLUMN_INFO.get(name)
    if factory is None:
        return None
    return factory()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_tui/test_column_info.py -v
```

Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/column_info.py tests/test_tui/test_column_info.py
git commit -m "feat(tui): ColumnInfo registry with universal entry (#167)"
```

---

## Task 2: ColumnInfoModal widget

**Files:**
- Create: `src/agent_toolkit_tui/widgets/column_info_modal.py`
- Modify: `src/agent_toolkit_tui/widgets/__init__.py`

- [ ] **Step 1: Write the failing Pilot test**

Create `tests/test_tui/test_column_info_modal.py`:

```python
"""Pilot tests for ColumnInfoModal."""
from __future__ import annotations

import pytest

from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal


@pytest.mark.asyncio
async def test_modal_renders_title_and_lines():
    from textual.app import App

    info = get_column_info("universal")
    assert info is not None

    class _A(App):
        def on_mount(self) -> None:
            self.push_screen(ColumnInfoModal(info))

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        # Title rendered.
        rendered = a.screen_stack[-1].query_one("#column-info-title").renderable
        assert "Universal" in str(rendered)
        # Body contains at least one harness name.
        body = a.screen_stack[-1].query_one("#column-info-body").renderable
        assert "claude-code" in str(body)


@pytest.mark.asyncio
async def test_modal_escape_closes():
    from textual.app import App

    info = get_column_info("universal")
    assert info is not None

    class _A(App):
        def on_mount(self) -> None:
            self.push_screen(ColumnInfoModal(info))

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        # Modal is on top of the default screen.
        assert len(a.screen_stack) == 2
        await pilot.press("escape")
        await pilot.pause()
        assert len(a.screen_stack) == 1


@pytest.mark.asyncio
async def test_modal_i_key_closes():
    """Pressing `i` again toggles the modal closed (symmetry with opening)."""
    from textual.app import App

    info = get_column_info("universal")
    assert info is not None

    class _A(App):
        def on_mount(self) -> None:
            self.push_screen(ColumnInfoModal(info))

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        assert len(a.screen_stack) == 2
        await pilot.press("i")
        await pilot.pause()
        assert len(a.screen_stack) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_tui/test_column_info_modal.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_tui.widgets.column_info_modal'`.

- [ ] **Step 3: Implement the modal**

Create `src/agent_toolkit_tui/widgets/column_info_modal.py`:

```python
"""Modal screen that shows ColumnInfo for a SkillGrid column.

Modeled after ConfirmDiscardScreen in app.py — same idiom for a tiny
disclosure surface. `esc` and `i` both close. Read-only; no actions.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from agent_toolkit_tui.column_info import ColumnInfo


class ColumnInfoModal(ModalScreen[None]):
    """Read-only popup listing the harnesses (or other content) in a column."""

    DEFAULT_CSS = """
    ColumnInfoModal {
        align: center middle;
    }
    ColumnInfoModal > Vertical {
        background: $panel;
        border: round $primary;
        padding: 1 2;
        width: 60;
        height: auto;
        max-height: 80%;
    }
    ColumnInfoModal #column-info-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    ColumnInfoModal #column-info-body {
        width: 100%;
        height: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("i", "close", "Close"),
    ]

    def __init__(self, info: ColumnInfo) -> None:
        super().__init__()
        self._info = info

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._info.title, id="column-info-title")
            yield Static("\n".join(self._info.lines), id="column-info-body")

    def action_close(self) -> None:
        self.dismiss(None)
```

Update `src/agent_toolkit_tui/widgets/__init__.py`:

```python
"""Textual widgets for agent-toolkit-tui."""

from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal
from agent_toolkit_tui.widgets.scope_toggle import ScopeToggle
from agent_toolkit_tui.widgets.skill_grid import SkillGrid

__all__ = ["ColumnInfoModal", "ScopeToggle", "SkillGrid"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_tui/test_column_info_modal.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/widgets/column_info_modal.py \
        src/agent_toolkit_tui/widgets/__init__.py \
        tests/test_tui/test_column_info_modal.py
git commit -m "feat(tui): ColumnInfoModal read-only popup (#167)"
```

---

## Task 3: Wire SkillGrid — glyph in label + `i` binding

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/skill_grid.py`
- Test: `tests/test_tui/test_skill_grid_column_info.py` (new)

- [ ] **Step 1: Write the failing Pilot tests**

Create `tests/test_tui/test_skill_grid_column_info.py`:

```python
"""Pilot tests for SkillGrid's column-info wiring."""
from __future__ import annotations

import pytest

from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _row(slug: str, *, scope: str = "global") -> SkillRow:
    cells = {(a, scope): SkillCell(linked=False, drift=False, skipped=False)
             for a in INTERACTIVE_AGENTS}
    return SkillRow(
        slug=slug, source=f"x/{slug}", ref="main",
        state="clean", cells=cells,
    )


@pytest.mark.asyncio
async def test_universal_column_label_has_info_glyph():
    """The universal column label includes the ⓘ glyph; others do not."""
    from textual.app import App
    from textual.widgets import DataTable

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        # Layout: slug | universal | claude-code | pi | state
        assert "ⓘ" in labels[1], f"universal label missing glyph: {labels[1]!r}"
        assert "ⓘ" not in labels[2], f"claude-code label has glyph: {labels[2]!r}"
        assert "ⓘ" not in labels[3], f"pi label has glyph: {labels[3]!r}"


@pytest.mark.asyncio
async def test_press_i_on_universal_column_opens_modal():
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="alpha", agent_name="universal")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert any(isinstance(s, ColumnInfoModal) for s in a.screen_stack), \
            "ColumnInfoModal not pushed"


@pytest.mark.asyncio
async def test_press_i_on_claude_code_column_is_noop():
    """No info registered for claude-code → pressing i does nothing."""
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="alpha", agent_name="claude-code")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert not any(isinstance(s, ColumnInfoModal) for s in a.screen_stack)


@pytest.mark.asyncio
async def test_press_i_on_slug_column_is_noop():
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=0)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert not any(isinstance(s, ColumnInfoModal) for s in a.screen_stack)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_tui/test_skill_grid_column_info.py -v
```

Expected: FAIL — universal column label has no `ⓘ`; `i` is unbound, so the modal never pushes.

- [ ] **Step 3: Modify `skill_grid.py` — glyph in label**

Edit `src/agent_toolkit_tui/widgets/skill_grid.py`:

a) Add an import at the top of the file, alongside the existing imports:

```python
from agent_toolkit_tui.column_info import COLUMN_INFO, get_column_info
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal
```

b) Add a module-level constant near the existing glyph constants:

```python
_INFO_GLYPH = "ⓘ"
```

c) Inside `_rebuild`, change the column-add loop (currently lines 222-226) from:

```python
for agent in INTERACTIVE_AGENTS:
    # Use "universal" verbatim for the bundle column (lowercase, per spec).
    # Other agents use their catalog display_name.
    label = "universal" if agent == "universal" else AGENTS[agent].display_name
    table.add_column(label, width=14)
```

to:

```python
for agent in INTERACTIVE_AGENTS:
    # Use "universal" verbatim for the bundle column (lowercase, per spec).
    # Other agents use their catalog display_name.
    base = "universal" if agent == "universal" else AGENTS[agent].display_name
    label = f"{_INFO_GLYPH} {base}" if agent in COLUMN_INFO else base
    table.add_column(label, width=14)
```

- [ ] **Step 4: Modify `skill_grid.py` — `i` binding + action**

Edit `src/agent_toolkit_tui/widgets/skill_grid.py`:

a) Add a new `Binding` to the `BINDINGS` list:

```python
BINDINGS = [
    Binding("space", "toggle_cell", "Toggle", priority=True),
    Binding("a", "toggle_column", "All/None", priority=True),
    Binding("i", "open_column_info", "Info", priority=True),
]
```

b) Add a new action method after `action_toggle_column`:

```python
def action_open_column_info(self) -> None:
    """Open ColumnInfoModal for the column under the cursor, if registered."""
    try:
        table = self.query_one("#skill-table", DataTable)
    except Exception:
        return
    col = table.cursor_coordinate.column
    agent = self._agent_for_column(col)
    if agent is None:
        return
    info = get_column_info(agent)
    if info is None:
        return
    self.app.push_screen(ColumnInfoModal(info))
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_tui/test_skill_grid_column_info.py -v
```

Expected: PASS (4 tests).

- [ ] **Step 6: Re-run the existing SkillGrid suite to confirm no regression**

```bash
uv run pytest tests/test_tui -v
```

Expected: ALL PASS — the existing `test_skill_grid_apply.py` and `test_skill_state.py` continue to pass.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_tui/widgets/skill_grid.py \
        tests/test_tui/test_skill_grid_column_info.py
git commit -m "feat(tui): info glyph + i-key on SkillGrid universal column (#167)"
```

---

## Task 4: Manual TUI smoke + full repo suite

**Files:** none modified.

This task is verification, not implementation. It ensures the artifact runs end-to-end.

- [ ] **Step 1: Run the full repo suite**

```bash
uv run pytest -q
```

Expected: ALL PASS. If any pre-existing test fails, **stop** and report — do not paper over.

- [ ] **Step 2: Run the TUI briefly and capture an artifact**

```bash
# From the worktree root.
mkdir -p assets/verification/167
# Headless smoke: just import + instantiate to confirm no compose-time crash.
uv run python -c "
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.column_info import get_column_info
print('universal info title:', get_column_info('universal').title)
print('universal info lines:')
for line in get_column_info('universal').lines:
    print('  ', line)
print('TUIApp instantiates:', TUIApp().__class__.__name__)
" | tee assets/verification/167/smoke.txt
```

Expected: prints the title `Universal bundle`, a list of harnesses, and confirms `TUIApp` instantiates without error. If any line raises, **stop** and surface the traceback.

- [ ] **Step 3: Commit (if anything in `assets/` should be tracked — usually no)**

`assets/verification/` is gitignored by the flow's Step 9 (verify) — do not commit. The smoke artifact stays in the worktree for the PR reviewer to inspect via the verification trail.

---

## Self-Review

**Spec coverage:**
- DoD #1 (`ⓘ` glyph next to universal header) → Task 3 Step 3.
- DoD #2 (pressing key opens modal listing harnesses) → Task 3 Step 4 + Task 2.
- DoD #3 (reusable pattern, one entry to add another column) → Task 1's registry + Task 3's `if agent in COLUMN_INFO` check.
- DoD #4 (Pilot test asserts glyph + modal contents) → `test_skill_grid_column_info.py` + `test_column_info_modal.py`.
- No regression in existing tests → Task 3 Step 6 + Task 4 Step 1.

**Placeholder scan:** None. All file paths, line numbers, code blocks, and shell commands are concrete.

**Type/name consistency:**
- `ColumnInfo` (frozen dataclass, fields `title: str`, `lines: list[str]`) — used identically in `column_info.py`, `column_info_modal.py`, and tests.
- `get_column_info(name) -> ColumnInfo | None` — same signature wherever called.
- `COLUMN_INFO` is a `dict[str, Callable[[], ColumnInfo]]` (factories) — registry membership check `agent in COLUMN_INFO` in `skill_grid.py` checks the same dict.
- `_INFO_GLYPH = "ⓘ"` — single source of truth in `skill_grid.py`; tests assert the literal `"ⓘ"`.
- `action_open_column_info` matches binding `"i" → open_column_info`.

**Open question from spec — modal vs inline panel.** Resolved: **modal**, matching the existing `ConfirmDiscardScreen` pattern. No inline panel inside `SkillGrid`.

**Open question from spec — glyph fallback for legacy terminals.** Deferred. `ⓘ` (U+24D8) is in standard Unicode and renders on every terminal AJ uses (iTerm2, Kitty, Ghostty, macOS Terminal). If a user reports a missing glyph, swap the single constant `_INFO_GLYPH` — no other code changes needed.

---

## Execution Handoff

Per flow Step 6, this plan is handed to **superpowers:subagent-driven-development** — one subagent per task with the fresh-context discipline that requires.
