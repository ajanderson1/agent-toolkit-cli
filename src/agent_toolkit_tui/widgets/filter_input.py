"""Shared TUI filter input for asset grids."""
from __future__ import annotations

from textual import events
from textual.css.query import NoMatches
from textual.widgets import DataTable, Input


class GridFilterInput(Input):
    """Filter box that hands focus to its sibling table on Down / Tab."""

    def __init__(
        self,
        *,
        table_selector: str,
        placeholder: str = "filter…",
        id: str | None = None,
    ) -> None:
        super().__init__(placeholder=placeholder, id=id)
        self.table_selector = table_selector

    def on_key(self, event: events.Key) -> None:
        if event.key in ("down", "tab"):
            try:
                self.screen.query_one(self.table_selector, DataTable).focus()
            except NoMatches:
                return
            event.stop()
            event.prevent_default()
