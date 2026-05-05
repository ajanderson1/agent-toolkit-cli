"""Left sidebar — selectable list of asset kinds with counts."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import ListItem, ListView, Static

from agent_toolkit_tui.messages import KindChanged
from agent_toolkit_tui.state import InventoryState

KINDS = ("skill", "agent", "command", "hook", "plugin", "mcp", "pi-extension")
KIND_LABELS = {"skill": "Skills", "agent": "Agents", "command": "Commands",
                "hook": "Hooks", "plugin": "Plugins", "mcp": "MCPs",
                "pi-extension": "Pi Ext"}


class KindsSidebar(Vertical):
    """Vertical list of kinds. Selection emits KindChanged."""

    DEFAULT_CSS = """
    KindsSidebar { width: 18; border: round $primary; }
    """

    def __init__(self, state: InventoryState, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._state = state
        self._counts = self._count(state)

    @staticmethod
    def _count(state: InventoryState) -> dict[str, int]:
        out = {k: 0 for k in KINDS}
        for r in state.rows:
            if r.kind in out:
                out[r.kind] += 1
        return out

    def compose(self) -> ComposeResult:
        yield ListView(
            *[ListItem(Static(f"{KIND_LABELS[k]:<10} {self._counts[k]:>3}"), id=f"kind-{k}")
              for k in KINDS],
            id="kinds-list",
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is None or event.item.id is None:
            return
        kind = event.item.id.removeprefix("kind-")
        self.post_message(KindChanged(kind=kind))

    def update_state(self, state: InventoryState) -> None:
        """Re-render counts after a refresh."""
        self._state = state
        self._counts = self._count(state)
        # Update the Static label text inside each existing ListItem in place
        # to avoid DOM ID-uniqueness issues from clear() + append().
        for k in KINDS:
            item = self.query_one(f"#kind-{k}", ListItem)
            item.query_one(Static).update(f"{KIND_LABELS[k]:<10} {self._counts[k]:>3}")
