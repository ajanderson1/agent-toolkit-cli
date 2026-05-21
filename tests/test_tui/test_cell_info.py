"""Pilot tests for the CellInfoScreen modal."""
from __future__ import annotations

import pytest

from agent_toolkit_tui.screens.cell_info import CellInfoScreen


@pytest.mark.asyncio
async def test_modal_renders_title_and_body():
    from textual.app import App
    pushed: list[CellInfoScreen] = []

    class _A(App):
        def on_mount(self):
            screen = CellInfoScreen(
                title="demo · claude-code @ global",
                body_markup="Linked.\nPath: /tmp/x",
            )
            pushed.append(screen)
            self.push_screen(screen)

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        assert pushed
        text = pushed[0].query_one("#cell-info-body").content
        # Rich Text or str — coerce both.
        rendered = str(text)
        assert "Linked." in rendered
        assert "/tmp/x" in rendered


@pytest.mark.asyncio
async def test_modal_dismisses_on_escape():
    from textual.app import App

    class _A(App):
        def on_mount(self):
            self.push_screen(CellInfoScreen(title="t", body_markup="b"))

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(a.screen, CellInfoScreen)
