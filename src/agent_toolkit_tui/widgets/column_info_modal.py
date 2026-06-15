"""Modal screen that shows ColumnInfo for a SkillGrid column.

Modeled after ConfirmDiscardScreen in app.py — same idiom for a tiny
disclosure surface. `esc` and `i` both close. Read-only; no actions.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
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
        height: auto;
        max-height: 80%;
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
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("i", "close", "Close"),
    ]

    def __init__(self, info: ColumnInfo) -> None:
        super().__init__()
        self._info = info

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._info.title, id="column-info-title")
            yield Static("\n".join(self._info.lines), id="column-info-body")

    def action_close(self) -> None:
        self.dismiss(None)
