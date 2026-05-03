"""Top row — scope radio + harness column-visibility checkboxes."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Checkbox, RadioButton, RadioSet, Static

from agent_toolkit_tui.messages import HarnessVisibilityChanged, ScopeChanged
from agent_toolkit_tui.state import InventoryState


class HarnessPicker(Horizontal):
    """Scope (user/project) + which harness columns are visible."""

    DEFAULT_CSS = """
    HarnessPicker { height: 6; border: round $primary; padding: 0 1; }
    HarnessPicker > Static { width: auto; margin: 0 1; }
    HarnessPicker RadioSet { width: 24; }
    HarnessPicker RadioSet > RadioButton.-on { background: $accent; color: $text; }
    HarnessPicker .harness-cb { margin-left: 1; }
    """

    def __init__(self, state: InventoryState, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._state = state

    def compose(self) -> ComposeResult:
        yield Static("[b]Scope[/b]")
        with RadioSet(id="scope-radio"):
            yield RadioButton("USER", id="scope-user", value=True)
            yield RadioButton("PROJECT", id="scope-project")
        yield Static("Harnesses:")
        for h in self._state.all_harnesses:
            yield Checkbox(h, id=f"hcb-{h}", value=True, classes="harness-cb")

    def on_mount(self) -> None:
        # Remove Tab focus from scope/harness controls — sidebar and grid only.
        for widget in self.query("RadioSet, Checkbox"):
            widget.can_focus = False

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.pressed.id == "scope-user":
            self.post_message(ScopeChanged(scope="user"))
        elif event.pressed.id == "scope-project":
            self.post_message(ScopeChanged(scope="project"))

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id and event.checkbox.id.startswith("hcb-"):
            harness = event.checkbox.id.removeprefix("hcb-")
            self.post_message(HarnessVisibilityChanged(harness=harness, visible=event.value))
