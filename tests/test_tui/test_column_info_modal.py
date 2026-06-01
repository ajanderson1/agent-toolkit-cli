"""Pilot tests for ColumnInfoModal."""
from __future__ import annotations

import pytest

from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal


@pytest.mark.asyncio
async def test_modal_renders_title_and_lines():
    from textual.app import App

    # Token stays "universal" (load-bearing bundle key); only the display label
    # changed to "General" in the v3 rename (#304 bug 3).
    info = get_column_info("universal")
    assert info is not None

    class _A(App):
        def on_mount(self) -> None:
            self.push_screen(ColumnInfoModal(info))

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        # Title rendered.
        rendered = a.screen_stack[-1].query_one("#column-info-title").render()
        assert "General" in str(rendered)
        # Body contains at least one harness name.
        body = a.screen_stack[-1].query_one("#column-info-body").render()
        assert "amp" in str(body)


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
