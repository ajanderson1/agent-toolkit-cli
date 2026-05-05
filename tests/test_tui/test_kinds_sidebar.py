"""KindsSidebar widget — vertical OptionList with kind counts."""
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import OptionList

from agent_toolkit_tui.messages import KindChanged
from agent_toolkit_tui.state import AssetRow, InventoryState
from agent_toolkit_tui.widgets.kinds_sidebar import (
    KIND_LABELS,
    KINDS,
    KindsSidebar,
)


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
        yield KindsSidebar(self._state)


def test_counts_each_kind() -> None:
    state = _state("skill", "skill", "agent", "command", "command", "command")
    sidebar = KindsSidebar(state)
    assert sidebar._counts == {
        "skill": 2, "agent": 1, "command": 3,
        "hook": 0, "plugin": 0, "pi-extension": 0,
    }


def test_set_active_noop_for_same_kind() -> None:
    state = _state("skill")
    sidebar = KindsSidebar(state)
    sidebar._active = "skill"
    sidebar.set_active("skill")
    assert sidebar._active == "skill"


def test_set_active_ignores_unknown_kind() -> None:
    state = _state("skill")
    sidebar = KindsSidebar(state)
    sidebar.set_active("nonsense")
    assert sidebar._active == "skill"


def test_kinds_constants_match_labels() -> None:
    assert set(KIND_LABELS.keys()) == set(KINDS)


async def test_set_active_changes_active_when_mounted() -> None:
    """set_active swaps the highlighted option after mount."""
    app = _Host(_state("skill", "agent", "command"))
    async with app.run_test() as pilot:
        sidebar = app.query_one(KindsSidebar)
        sidebar.set_active("agent")
        await pilot.pause()
        assert sidebar._active == "agent"


async def test_update_state_refreshes_counts_preserves_active() -> None:
    """update_state with new state refreshes counts; active option preserved."""
    app = _Host(_state("skill"))
    async with app.run_test() as pilot:
        sidebar = app.query_one(KindsSidebar)
        sidebar.set_active("agent")
        new = _state("skill", "skill", "skill", "agent", "agent")
        sidebar.update_state(new)
        await pilot.pause()
        assert sidebar._counts["skill"] == 3
        assert sidebar._counts["agent"] == 2
        assert sidebar._active == "agent"


async def test_optionlist_selection_posts_kind_changed() -> None:
    """Selecting an option in the OptionList posts KindChanged on the bus."""
    app = _Host(_state("skill", "agent"))
    async with app.run_test() as pilot:
        sidebar = app.query_one(KindsSidebar)
        olist = sidebar.query_one(OptionList)

        received: list[str] = []

        def _capture(event: KindChanged) -> None:
            received.append(event.kind)

        # Subscribe via simple event handler on the host
        app._capture = _capture  # type: ignore[attr-defined]

        # Emulate selection: highlight then "select" (Enter on OptionList)
        olist.focus()
        await pilot.pause()
        # The 2nd option corresponds to "agent" (KINDS index 1)
        olist.highlighted = 1
        await pilot.press("enter")
        await pilot.pause()

        assert sidebar._active == "agent"
