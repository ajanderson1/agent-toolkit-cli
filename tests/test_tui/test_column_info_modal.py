"""Pilot tests for ColumnInfoModal."""
from __future__ import annotations

import pytest

from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal


@pytest.mark.asyncio
async def test_modal_renders_title_and_lines():
    from textual.app import App

    info = get_column_info("standard", asset_type="skill", context={"scope": "global"})

    class _A(App):
        def on_mount(self) -> None:
            self.push_screen(ColumnInfoModal(info))

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        # Title rendered.
        rendered = a.screen_stack[-1].query_one("#column-info-title").render()
        assert "Standard" in str(rendered)
        # Body contains at least one harness name.
        body = a.screen_stack[-1].query_one("#column-info-body").render()
        assert "Amp" in str(body)


@pytest.mark.asyncio
async def test_modal_escape_closes():
    from textual.app import App

    info = get_column_info("standard", asset_type="skill", context={"scope": "global"})

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
async def test_long_modal_body_scrolls_in_a_small_terminal():
    """The 39-harness Instructions panel must remain fully reachable (#479)."""
    from textual.app import App
    from textual.containers import Vertical

    info = get_column_info(
        "standard",
        asset_type="instruction",
        context={"scope": "project", "global_linked": True},
    )

    class _A(App):
        def on_mount(self) -> None:
            self.push_screen(ColumnInfoModal(info))

    app = _A()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        panel = app.screen.query_one(Vertical)
        assert panel.virtual_size.height > panel.size.height
        assert panel.allow_vertical_scroll

        panel.scroll_end(animate=False)
        await pilot.pause()
        assert panel.scroll_y == panel.max_scroll_y
        assert panel.scroll_y > 0


@pytest.mark.asyncio
async def test_modal_i_key_closes():
    """Pressing `i` closes a mouse-opened column modal."""
    from textual.app import App

    info = get_column_info("standard", asset_type="skill", context={"scope": "global"})

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
