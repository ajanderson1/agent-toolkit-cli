"""Pilot tests: the Kind sidebar highlight tracks the active grid (#328).

Before the fix, the sidebar `OptionList#kinds-list` was never told which option
was active, so its highlight defaulted to the first option (`instruction`) while
`on_mount` rendered the `SkillGrid`. Pane showed **skill**, sidebar highlighted
**instruction** — they diverged. The fix syncs the highlight inside `_show_kind`
(the choke point both mount and `action_kind` already call), so the highlight
always tracks the displayed grid, not just the last clicked option.

Indices are resolved by option id (`kind-<kind>`) rather than hardcoded, so the
tests survive any future reordering of the sidebar options.
"""
from __future__ import annotations

import pytest
from textual.widgets import OptionList

from agent_toolkit_tui.app import TUIApp


def _index_of(option_list: OptionList, kind: str) -> int:
    return option_list.get_option_index(f"kind-{kind}")


@pytest.mark.asyncio
async def test_mount_highlights_active_skill_kind():
    """On mount the pane shows the SkillGrid, so the sidebar must highlight
    `skill` — not the default first option (`instruction`)."""
    app = TUIApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        kinds = app.query_one("#kinds-list", OptionList)
        assert kinds.highlighted == _index_of(kinds, "skill"), (
            f"sidebar highlight {kinds.highlighted} does not match active "
            f"kind 'skill' (index {_index_of(kinds, 'skill')})"
        )


@pytest.mark.asyncio
async def test_action_kind_syncs_highlight():
    """Switching the active kind must move the sidebar highlight in lock-step
    for every kind, regardless of how the switch was triggered."""
    app = TUIApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        kinds = app.query_one("#kinds-list", OptionList)

        for kind in ("instruction", "pi-extension", "agent", "skill"):
            app.action_kind(kind)
            await pilot.pause()
            assert kinds.highlighted == _index_of(kinds, kind), (
                f"after action_kind({kind!r}) the highlight is "
                f"{kinds.highlighted}, expected {_index_of(kinds, kind)}"
            )
