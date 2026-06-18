from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_sidebar_uses_plural_title_case_asset_labels():
    from textual.widgets import OptionList

    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        sidebar = app.query_one("#asset-types-list", OptionList)
        labels = [str(option.prompt) for option in sidebar.options if not option.disabled]
        assert labels == ["Instructions", "Skills", "Commands", "Pi Extensions", "Agents", "MCPs"]


@pytest.mark.asyncio
async def test_content_header_uses_plural_asset_label():
    from textual.widgets import Static

    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("pi-extension")
        await pilot.pause()
        header = str(app.query_one("#content-header", Static).render())
        assert "Pi Extensions" in header
