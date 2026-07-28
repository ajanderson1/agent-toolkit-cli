from __future__ import annotations

import pytest

from agent_toolkit_tui.app import TUIApp

CASES = [
    ("instruction", "instruction-filter"),
    ("skill", "skill-filter"),
    ("command", "command-filter"),
    ("pi-extension", "pi-filter"),
    ("agent", "agent-filter"),
    ("mcp", "mcp-filter"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("asset_type", "filter_id"), CASES)
async def test_action_asset_type_focuses_that_tabs_filter(asset_type, filter_id):
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type(asset_type)
        await pilot.pause()
        assert app.focused is not None
        assert app.focused.id == filter_id


@pytest.mark.asyncio
async def test_startup_focuses_skill_filter():
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.focused is not None
        assert app.focused.id == "skill-filter"


@pytest.mark.asyncio
async def test_reselecting_active_tab_refocuses_filter():
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("agent")
        await pilot.pause()
        app.query_one("#asset-types-list").focus()
        await pilot.pause()
        assert app.focused.id == "asset-types-list"

        app.action_asset_type("agent")  # already active
        await pilot.pause()
        assert app.focused is not None
        assert app.focused.id == "agent-filter"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "asset_type", "filter_id"),
    [
        ("1", "instruction", "instruction-filter"),
        ("2", "command", "command-filter"),
        ("3", "skill", "skill-filter"),
        ("4", "agent", "agent-filter"),
        ("5", "mcp", "mcp-filter"),
        ("6", "pi-extension", "pi-filter"),
    ],
)
async def test_number_key_route_switches_and_focuses_filter(key, asset_type, filter_id):
    app = TUIApp()
    async with app.run_test() as pilot:
        sidebar = app.query_one("#asset-types-list")
        sidebar.focus()
        await pilot.pause()
        await pilot.press(key)
        await pilot.pause()
        assert app._active_asset_type == asset_type
        assert sidebar.highlighted == sidebar.get_option_index(f"asset-type-{asset_type}")
        assert app.focused is not None
        assert app.focused.id == filter_id


@pytest.mark.asyncio
async def test_refocus_does_not_disturb_filter_text_or_pending():
    """R5 is a property of the focus call, not of a tab switch.

    A real switch runs `_refresh_active_view()` -> `set_rows()`, which clears
    pending BY EXISTING CONTRACT (app.py). So assert on the already-active
    (early-return) path, where no refresh runs. Asserting across a real switch
    would encode a false expectation and fail for a reason unrelated to #477.
    """
    from textual.widgets import Input

    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("agent")
        await pilot.pause()
        app.query_one("#agent-filter", Input).value = "zzz"
        await pilot.pause()
        grid = app.query_one("#agent-grid")
        pending_before = dict(grid.pending_entries())
        scope_before = grid._scope

        app.query_one("#asset-types-list").focus()
        await pilot.pause()
        app.action_asset_type("agent")  # re-select: focus only, no refresh
        await pilot.pause()

        assert app.focused.id == "agent-filter"
        assert app.query_one("#agent-filter", Input).value == "zzz"
        assert dict(grid.pending_entries()) == pending_before
        assert grid._scope == scope_before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("asset_type", "filter_id", "table_id"),
    [
        ("instruction", "instruction-filter", "instruction-table"),
        ("skill", "skill-filter", "skill-table"),
        ("command", "command-filter", "command-table"),
        ("pi-extension", "pi-filter", "pi-table"),
        ("agent", "agent-filter", "agent-table"),
        ("mcp", "mcp-filter", "mcp-table"),
    ],
)
async def test_escape_hatch_from_filter_to_table(asset_type, filter_id, table_id):
    """R5a: the caret now starts in an Input on every tab, so Down/Tab/Enter
    must all reach the table, and `/` must come back."""
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type(asset_type)
        await pilot.pause()
        for key in ("down", "tab", "enter"):
            app.action_focus_filter()
            await pilot.pause()
            assert app.focused.id == filter_id
            await pilot.press(key)
            await pilot.pause()
            assert app.focused is not None, f"{key} lost focus entirely"
            assert app.focused.id == table_id, f"{key} did not reach the table"
        await pilot.press("slash")
        await pilot.pause()
        assert app.focused.id == filter_id
