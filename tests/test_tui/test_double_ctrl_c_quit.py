from __future__ import annotations

from types import MethodType
from typing import TYPE_CHECKING

import pytest
from textual.widgets import DataTable

import agent_toolkit_tui.app as app_module
from agent_toolkit_tui.app import ConfirmDiscardScreen, TUIApp
from agent_toolkit_tui.widgets import SkillGrid

if TYPE_CHECKING:
    from textual.notifications import Notification


def spy_quit(app: TUIApp) -> list[str]:
    calls: list[str] = []

    def fake_action_quit(self: TUIApp) -> None:
        calls.append("quit")

    app.action_quit = MethodType(fake_action_quit, app)
    return calls


def spy_notify(app: TUIApp) -> list[str]:
    messages: list[str] = []
    original = app.notify

    def fake_notify(message: str, *args: object, **kwargs: object) -> Notification:
        messages.append(message)
        return original(message, *args, **kwargs)

    app.notify = fake_notify
    return messages


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


@pytest.mark.asyncio
async def test_ctrl_c_after_timeout_starts_fresh(monkeypatch):
    times = iter([100.0, 102.0])
    monkeypatch.setattr(app_module, "monotonic", lambda: next(times), raising=False)

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
