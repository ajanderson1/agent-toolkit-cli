"""Pilot tests: the asset-type sidebar highlight tracks the active grid (#328).

Before the fix, the sidebar `OptionList#asset-types-list` was never told which option
was active, so its highlight defaulted to the first option (`instruction`) while
`on_mount` rendered the `SkillGrid`. Pane showed **skill**, sidebar highlighted
**instruction** — they diverged. The fix syncs the highlight inside `_show_asset_type`
(the choke point both mount and `action_asset_type` already call), so the highlight
always tracks the displayed grid, not just the last clicked option.

Indices are resolved by option id (`asset-type-<asset-type>`) rather than hardcoded, so the
tests survive any future reordering of the sidebar options.
"""
from __future__ import annotations

import pytest
from textual.widgets import OptionList

from agent_toolkit_tui.app import TUIApp


def _index_of(option_list: OptionList, asset_type: str) -> int:
    return option_list.get_option_index(f"asset-type-{asset_type}")


@pytest.mark.asyncio
async def test_mount_highlights_active_skill_asset_type():
    """On mount the pane shows the SkillGrid, so the sidebar must highlight
    `skill` — not the default first option (`instruction`)."""
    app = TUIApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        asset_types_list = app.query_one("#asset-types-list", OptionList)
        assert asset_types_list.highlighted == _index_of(asset_types_list, "skill"), (
            f"sidebar highlight {asset_types_list.highlighted} does not match active "
            f"asset type 'skill' (index {_index_of(asset_types_list, 'skill')})"
        )


@pytest.mark.asyncio
async def test_action_asset_type_syncs_highlight():
    """Switching the active asset type must move the sidebar highlight in lock-step
    for every asset type, regardless of how the switch was triggered."""
    app = TUIApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        asset_types_list = app.query_one("#asset-types-list", OptionList)

        for asset_type in ("instruction", "pi-extension", "agent", "skill"):
            app.action_asset_type(asset_type)
            await pilot.pause()
            assert asset_types_list.highlighted == _index_of(asset_types_list, asset_type), (
                f"after action_asset_type({asset_type!r}) the highlight is "
                f"{asset_types_list.highlighted}, expected {_index_of(asset_types_list, asset_type)}"
            )
