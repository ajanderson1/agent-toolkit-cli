"""KindsTabs widget — single-line tab strip across the top."""
from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult

from agent_toolkit_tui.messages import KindChanged
from agent_toolkit_tui.state import AssetRow, InventoryState
from agent_toolkit_tui.widgets.kinds_tabs import KIND_LABELS, KINDS, KindsTabs


def _row(kind: str, slug: str) -> AssetRow:
    return AssetRow(
        slug=slug,
        kind=kind,
        origin="first-party",
        description="",
        path=Path("/x"),
        declared_harnesses=("claude",),
        cells={},
    )


def _state(*kinds: str) -> InventoryState:
    return InventoryState(
        toolkit_root=Path("/repo"),
        rows=tuple(_row(k, f"{k}-{i}") for i, k in enumerate(kinds)),
        all_harnesses=("claude", "codex"),
    )


class _Host(App):
    def __init__(self, state: InventoryState) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        yield KindsTabs(self._state)


def test_counts_each_kind() -> None:
    state = _state("skill", "skill", "agent", "command", "command", "command")
    tabs = KindsTabs(state)
    assert tabs._counts == {
        "skill": 2, "agent": 1, "command": 3,
        "hook": 0, "plugin": 0, "pi-extension": 0,
    }


def test_build_markup_marks_active_kind() -> None:
    state = _state("skill", "agent")
    tabs = KindsTabs(state)
    rendered = tabs._build_markup()
    assert "[reverse][b] 1·Skills" in rendered
    assert "[dim]1[/]" in rendered  # 1 agent
    assert "[dim]0[/]" in rendered  # 0 hooks/plugins/etc


def test_set_active_noop_for_same_kind() -> None:
    state = _state("skill")
    tabs = KindsTabs(state)
    tabs._active = "skill"
    tabs.set_active("skill")
    assert tabs._active == "skill"


def test_set_active_ignores_unknown_kind() -> None:
    state = _state("skill")
    tabs = KindsTabs(state)
    tabs.set_active("nonsense")
    assert tabs._active == "skill"


def test_kinds_constants_match_labels() -> None:
    assert set(KIND_LABELS.keys()) == set(KINDS)


async def test_set_active_changes_active_when_mounted() -> None:
    """Mounted: set_active swaps the highlight and the rendered markup updates."""
    app = _Host(_state("skill", "agent", "command"))
    async with app.run_test() as pilot:
        tabs = app.query_one(KindsTabs)
        tabs.set_active("agent")
        await pilot.pause()
        assert tabs._active == "agent"
        assert "[reverse][b] 2·Agents" in tabs._build_markup()


async def test_update_state_refreshes_counts_preserves_active() -> None:
    """update_state with new state refreshes counts; active tab is preserved."""
    app = _Host(_state("skill"))
    async with app.run_test() as pilot:
        tabs = app.query_one(KindsTabs)
        tabs.set_active("agent")
        new = _state("skill", "skill", "skill", "agent", "agent")
        tabs.update_state(new)
        await pilot.pause()
        assert tabs._counts["skill"] == 3
        assert tabs._counts["agent"] == 2
        assert tabs._active == "agent"
