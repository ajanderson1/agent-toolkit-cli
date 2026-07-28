# TUI Modal Overlay Backdrop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore Textual's dim modal backdrop so info/confirm popups overlay the live grid instead of blanking it.

**Architecture:** CSS-only. The global `Screen { background: $surface; }` rule in `app.tcss` currently paints every screen — including `ModalScreen` subclasses — solid. Add an explicit `ModalScreen { background: $background 60%; }` rule immediately after it so type-specificity restores the framework dim for every modal. No Python behaviour change.

**Tech Stack:** Textual TCSS, pytest + pytest-asyncio, `TUIApp.run_test()` pilot, `screen.styles.background.a` for alpha assertions.

**Spec:** `docs/superpowers/specs/2026-07-28-488-tui-modal-overlay-backdrop.md`
**Issue:** #488 · **Size:** M (fix)

## File structure

- Modify: `src/agent_toolkit_tui/css/app.tcss`
  - keep `Screen { background: $surface; }`;
  - add `ModalScreen { background: $background 60%; }` immediately after.
- Create: `tests/test_tui/test_modal_overlay_backdrop.py`
  - assert base screen is opaque;
  - assert CellInfoScreen / ColumnInfoModal / ConfirmDiscardScreen resolve alpha ≈ 0.6;
  - assert SettingsScreen also dim (same rule);
  - assert dismiss returns to base screen with opaque background.

## Task 1: Failing tests first

**Files:**
- Create: `tests/test_tui/test_modal_overlay_backdrop.py`

- [ ] **Step 1: Write the test module**

```python
from __future__ import annotations

import pytest

from agent_toolkit_tui.app import ConfirmDiscardScreen, TUIApp
from agent_toolkit_tui.column_info import ColumnInfo
from agent_toolkit_tui.screens.cell_info import CellInfoScreen
from agent_toolkit_tui.screens.settings import SettingsScreen
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal


def _alpha(screen) -> float:
    return float(screen.styles.background.a)


@pytest.mark.asyncio
async def test_base_screen_is_opaque():
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert _alpha(app.screen) == 1.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "factory",
    [
        lambda: CellInfoScreen(title="t", body_markup="b"),
        lambda: ColumnInfoModal(ColumnInfo(title="T", lines=["line"])),
        lambda: ConfirmDiscardScreen(1),
    ],
    ids=["cell-info", "column-info", "confirm-discard"],
)
async def test_named_modals_use_dim_backdrop(factory):
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(factory())
        await pilot.pause()
        alpha = _alpha(app.screen)
        assert 0.0 < alpha < 1.0
        assert alpha == pytest.approx(0.6, abs=0.05)


@pytest.mark.asyncio
async def test_settings_screen_also_dims():
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(SettingsScreen(app.tui_settings))
        await pilot.pause()
        alpha = _alpha(app.screen)
        assert 0.0 < alpha < 1.0
        assert alpha == pytest.approx(0.6, abs=0.05)


@pytest.mark.asyncio
async def test_dismiss_restores_opaque_base():
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(CellInfoScreen(title="t", body_markup="b"))
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert _alpha(app.screen) == 1.0
```

- [ ] **Step 2: Run tests — expect FAIL (alpha == 1.0 on modals)**

```bash
uv run pytest tests/test_tui/test_modal_overlay_backdrop.py -q
```

Expected: base/dismiss may pass; named-modal + settings tests FAIL with alpha 1.0.

## Task 2: CSS fix

**Files:**
- Modify: `src/agent_toolkit_tui/css/app.tcss`

- [ ] **Step 1: Insert ModalScreen rule**

Immediately after the existing `Screen` block, add:

```css
/* ModalScreens must keep Textual's dim translucent backdrop so the live
   grid stays visible underneath info/confirm popups (#488). The broader
   Screen rule above would otherwise paint them solid $surface. */
ModalScreen {
    background: $background 60%;
}
```

Do not remove or alter the `Screen { background: $surface; }` block.
Do not edit the three modal Python classes.

- [ ] **Step 2: Re-run focused tests — expect PASS**

```bash
uv run pytest tests/test_tui/test_modal_overlay_backdrop.py -q
```

Expected: all green.

## Task 3: Regression slice + lint

- [ ] **Step 1: Related TUI tests**

```bash
uv run pytest tests/test_tui/test_cell_info.py tests/test_tui/test_column_info_modal.py tests/test_tui/test_double_ctrl_c_quit.py tests/test_tui/test_settings_screen.py tests/test_tui/test_modal_overlay_backdrop.py -q
```

Expected: all green.

- [ ] **Step 2: Lint (no Python change expected clean)**

```bash
uv run ruff check tests/test_tui/test_modal_overlay_backdrop.py
```

## Verification gate (firm)

| Field | Value |
|---|---|
| status | firm |
| climb | R0 |
| command | `uv run pytest tests/test_tui/test_modal_overlay_backdrop.py -q` |
| evidence | `assets/verification/488/` (pytest log) |
| visual judgment | optional manual: open `i` on a skill cell — grid visible under dim card |
