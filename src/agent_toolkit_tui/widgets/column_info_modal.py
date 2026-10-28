"""Modal screen that shows ColumnInfo for any TUI asset-grid column.

Modeled after ConfirmDiscardScreen in app.py — same idiom for a tiny
disclosure surface. `esc` and `i` both close. Read-only; no actions.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from agent_toolkit_tui.column_info import ColumnInfo


class ColumnInfoModal(ModalScreen[None]):
    """Read-only popup listing the harnesses (or other content) in a column."""

    DEFAULT_CSS = """
    ColumnInfoModal {
        align: center middle;
    }
    ColumnInfoModal > Vertical {
        background: $panel;
        border: round $primary;
        padding: 1 2;
        width: 60;
        max-width: 95%;
        height: auto;
        max-height: 80%;
    }
    ColumnInfoModal > Vertical > VerticalScroll {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
    }
    ColumnInfoModal #column-info-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    ColumnInfoModal #column-info-body {
        width: 100%;
        height: auto;
    }
    ColumnInfoModal #column-info-footer {
        margin-top: 1;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("i", "close", "Close"),
        Binding("up", "scroll_up", show=False),
        Binding("down", "scroll_down", show=False),
        Binding("pageup", "scroll_page_up", show=False),
        Binding("pagedown", "scroll_page_down", show=False),
    ]

    def __init__(self, info: ColumnInfo) -> None:
        super().__init__()
        self._info = info

    def compose(self) -> ComposeResult:
        with Vertical():
            with VerticalScroll():
                yield Static(self._info.title, id="column-info-title")
                yield Static(self._info.body_markup, id="column-info-body", markup=True)
            yield Static("↑/↓ or PgUp/PgDn scroll · Esc / i close", id="column-info-footer")

    def action_close(self) -> None:
        self.dismiss(None)

    def action_scroll_up(self) -> None:
        self.query_one(VerticalScroll).scroll_relative(y=-1, animate=False)

    def action_scroll_down(self) -> None:
        self.query_one(VerticalScroll).scroll_relative(y=1, animate=False)

    def action_scroll_page_up(self) -> None:
        self.query_one(VerticalScroll).scroll_relative(y=-self.size.height + 3, animate=False)

    def action_scroll_page_down(self) -> None:
        self.query_one(VerticalScroll).scroll_relative(y=self.size.height - 3, animate=False)
