"""Top-of-screen tab strip — replaces the old left sidebar.

Renders kinds as a single line of segments. The active kind is shown in
[reverse][b]; others are muted with their count in dim. Selection is driven
by the App's 1-6 keybindings; this widget posts KindChanged when its
update_state-tracked kind changes.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from agent_toolkit_tui.messages import KindChanged
from agent_toolkit_tui.state import InventoryState

KINDS = ("skill", "agent", "command", "hook", "plugin", "pi-extension")
KIND_LABELS = {
    "skill": "Skills",
    "agent": "Agents",
    "command": "Commands",
    "hook": "Hooks",
    "plugin": "Plugins",
    "pi-extension": "Pi Ext",
}


class KindsTabs(Vertical):
    """Single-line tab strip across the top, one tab per kind."""

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
        yield Static(self._build_markup(), id="kinds-tabs-line")

    def _build_markup(self) -> str:
        parts: list[str] = []
        for i, k in enumerate(KINDS, 1):
            label = KIND_LABELS[k]
            count = self._counts[k]
            if k == self._active:
                parts.append(f"[reverse][b] {i}·{label} {count} [/][/]")
            else:
                parts.append(f"  {i}·{label} [dim]{count}[/]")
        return "  ".join(parts)

    def set_active(self, kind: str) -> None:
        """Change which tab is highlighted. Posts KindChanged if it changed."""
        if kind == self._active or kind not in KINDS:
            return
        self._active = kind
        self.query_one("#kinds-tabs-line", Static).update(self._build_markup())
        self.post_message(KindChanged(kind=kind))

    def update_state(self, state: InventoryState) -> None:
        """Re-render counts after a refresh. Does not change active tab."""
        self._state = state
        self._counts = self._count(state)
        self.query_one("#kinds-tabs-line", Static).update(self._build_markup())
