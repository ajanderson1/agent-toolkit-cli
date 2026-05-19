"""ScopeToggle — paired-toggle widget for scope=project|user in the content header.

Replaces the old Rich [@click=…] markup chips that were embedded in
#content-header. Each scope is rendered as a Label with an explicit on_click
handler, so mouse hit-testing is unambiguous and we don't depend on Rich
action-link parsing inside a Static.
"""
from __future__ import annotations

from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label

SCOPES: tuple[str, ...] = ("project", "user")


class ScopeToggle(Horizontal):
    """Two-state toggle between 'project' and 'user' scopes.

    Composition: a Horizontal of two Labels, one per scope value. Active state
    is signalled via CSS class names (-active / -inactive) — both labels share
    the same shape and padding; only colour distinguishes them.

    Click handling: each Label's on_click handler dispatches to
    `self.app.action_scope(scope)`. The host app owns the scope state machine;
    this widget is a pure view + click-source.
    """

    DEFAULT_CSS: ClassVar[str] = ""

    def __init__(self, *, active: str = "project", id: str | None = None) -> None:
        super().__init__(id=id)
        if active not in SCOPES:
            raise ValueError(f"active must be one of {SCOPES}, got {active!r}")
        self._active: str = active
        self._toggle_id: str = id or "scope-toggle"

    def compose(self) -> ComposeResult:
        yield Label("scope:", classes="scope-toggle-label")
        for scope in SCOPES:
            label = Label(
                scope,
                id=f"{self._toggle_id}-{scope}",
                classes="scope-option " + ("-active" if scope == self._active else "-inactive"),
            )
            yield label

    def set_active(self, scope: str) -> None:
        """Re-paint to mark `scope` as active, the other as inactive."""
        if scope not in SCOPES:
            raise ValueError(f"scope must be one of {SCOPES}, got {scope!r}")
        self._active = scope
        for s in SCOPES:
            try:
                label = self.query_one(f"#{self._toggle_id}-{s}", Label)
            except Exception:
                continue
            label.remove_class("-active")
            label.remove_class("-inactive")
            label.add_class("-active" if s == scope else "-inactive")

    def on_click(self, event: events.Click) -> None:
        """Dispatch when a child Label is clicked.

        Textual bubbles the Click event up from the Label to this Horizontal.
        We identify the source by the event.widget.id and route to
        self.app.action_scope.
        """
        target = event.widget
        if target is None:
            return
        widget_id = getattr(target, "id", None)
        if not widget_id or not widget_id.startswith(f"{self._toggle_id}-"):
            return
        scope = widget_id[len(self._toggle_id) + 1 :]
        if scope not in SCOPES:
            return
        event.stop()
        self.app.action_scope(scope)
