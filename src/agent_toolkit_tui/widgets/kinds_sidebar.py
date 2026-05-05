"""Left-side OptionList that drives the content pane (V1 Navigator).

Posts KindChanged when the user selects a different kind.

Public API mirrors the dead KindsTabs widget so app.py only needs to swap
the import:
- __init__(state, *, id=None)
- set_active(kind) — change selection programmatically
- update_state(state) — re-render counts after a refresh
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from agent_toolkit_tui.messages import KindChanged
from agent_toolkit_tui.state import InventoryState

KINDS: tuple[str, ...] = (
    "skill", "agent", "command", "hook", "plugin", "pi-extension",
)
KIND_LABELS: dict[str, str] = {
    "skill": "Skills",
    "agent": "Agents",
    "command": "Commands",
    "hook": "Hooks",
    "plugin": "Plugins",
    "pi-extension": "Pi Ext",
}


class KindsSidebar(Vertical):
    """Vertical KINDS rail — Static header + OptionList of kinds with counts."""

    def __init__(self, state: InventoryState, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._state = state
        self._counts = self._count(state)
        self._active = "skill"

    @staticmethod
    def _count(state: InventoryState) -> dict[str, int]:
        out = {k: 0 for k in KINDS}
        for r in state.rows:
            if r.kind in out:
                out[r.kind] += 1
        return out

    def compose(self) -> ComposeResult:
        yield Static("KINDS", classes="rail-header")
        yield OptionList(*self._build_options(), id="kinds-list")

    def _build_options(self) -> list[Option]:
        opts: list[Option] = []
        for k in KINDS:
            label = KIND_LABELS[k]
            count = self._counts[k]
            opts.append(Option(f" {label:<10} {count:>3}", id=k))
        return opts

    def on_mount(self) -> None:
        try:
            olist = self.query_one("#kinds-list", OptionList)
            olist.highlighted = KINDS.index(self._active)
        except Exception:
            pass

    def set_active(self, kind: str) -> None:
        """Change selection programmatically. Posts KindChanged if it changes."""
        if kind == self._active or kind not in KINDS:
            return
        self._active = kind
        try:
            olist = self.query_one("#kinds-list", OptionList)
            olist.highlighted = KINDS.index(kind)
        except Exception:
            pass
        self.post_message(KindChanged(kind=kind))

    def update_state(self, state: InventoryState) -> None:
        """Re-render counts after a refresh. Does not change active option."""
        self._state = state
        self._counts = self._count(state)
        try:
            olist = self.query_one("#kinds-list", OptionList)
            olist.clear_options()
            olist.add_options(self._build_options())
            olist.highlighted = KINDS.index(self._active)
        except Exception:
            pass

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """User pressed Enter on an option — switch active kind."""
        if event.option.id and event.option.id in KINDS:
            self.set_active(event.option.id)
