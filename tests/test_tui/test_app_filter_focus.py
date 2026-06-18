from __future__ import annotations

import pytest

from agent_toolkit_tui.app import TUIApp


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("asset_type", "filter_id"),
    [
        ("instruction", "instruction-filter"),
        ("skill", "skill-filter"),
        ("command", "command-filter"),
        ("pi-extension", "pi-filter"),
        ("agent", "agent-filter"),
        ("mcp", "mcp-filter"),
    ],
)
async def test_slash_focuses_active_asset_filter(asset_type: str, filter_id: str):
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type(asset_type)
        await pilot.pause()

        await pilot.press("/")
        await pilot.pause()

        assert app.focused is not None
        assert app.focused.id == filter_id
