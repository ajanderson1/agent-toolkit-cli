"""Modal screens must dim over the live grid, not blank it (#488)."""
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
