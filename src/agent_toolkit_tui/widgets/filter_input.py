"""Shared TUI filter input for asset grids."""
from __future__ import annotations

from textual import events
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.widgets import DataTable, Input


class GridFilterInput(Input):
    """Filter box with terminal-style editing and table-focus shortcuts."""

    BINDINGS = [
        Binding("escape", "clear_filter", "Clear filter", show=False, priority=True),
        Binding(
            "alt+backspace",
            "delete_left_word",
            "Delete preceding word",
            show=False,
            priority=True,
        ),
    ]

    def __init__(
        self,
        *,
        table_selector: str,
        placeholder: str = "filter…",
        id: str | None = None,
    ) -> None:
        super().__init__(placeholder=placeholder, id=id)
        self.table_selector = table_selector

    def action_clear_filter(self) -> None:
        """Clear the active filter without moving focus away from the input."""
        self.value = ""

    def on_key(self, event: events.Key) -> None:
        if event.key in ("down", "tab"):
            try:
                self.screen.query_one(self.table_selector, DataTable).focus()
            except NoMatches:
                return
            event.stop()
            event.prevent_default()
