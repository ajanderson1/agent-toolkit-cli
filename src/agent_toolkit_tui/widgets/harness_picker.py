"""Top row — scope radio."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import RadioButton, RadioSet, Static

from agent_toolkit_tui.messages import ScopeChanged
from agent_toolkit_tui.state import InventoryState


class HarnessPicker(Horizontal):
    """Scope (user/project) selector."""

    DEFAULT_CSS = """
    HarnessPicker { height: 6; border: round $primary; padding: 0 1; }
    HarnessPicker > Static { width: auto; margin: 0 1; }
    HarnessPicker RadioSet { width: 24; }
    HarnessPicker RadioSet > RadioButton.-on { background: $accent; color: $text; }
    """

    def __init__(self, state: InventoryState, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._state = state

    def compose(self) -> ComposeResult:
        yield Static("[b]Scope[/b]")
        with RadioSet(id="scope-radio"):
            yield RadioButton("USER", id="scope-user")
            yield RadioButton("PROJECT", id="scope-project", value=True)

    def on_mount(self) -> None:
        # Remove Tab focus from scope controls — sidebar and grid only.
        for widget in self.query("RadioSet"):
            widget.can_focus = False

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.pressed.id == "scope-user":
            self.post_message(ScopeChanged(scope="user"))
        elif event.pressed.id == "scope-project":
            self.post_message(ScopeChanged(scope="project"))
