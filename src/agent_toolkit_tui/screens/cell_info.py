"""CellInfoScreen — modal that renders state-specific info for a SkillGrid cell."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static


def asset_info_body(
    *,
    asset_label: str,
    slug: str,
    description: str | None,
    description_location: str,
    source: str,
    ref: str | None,
    state: str,
    scope: str,
    extra_lines: list[str] | None = None,
) -> str:
    """Render the shared asset-level panel body used by every grid (#479)."""
    lines = [f"{asset_label} [b]{slug}[/]"]
    if description and description.strip():
        lines += ["", "Description:", description]
    else:
        lines += ["", f"No description in {description_location}."]
    lines += [
        "",
        f"Source: {source}",
        f"Ref:    {ref or '—'}",
        f"State ({scope}): {state}",
    ]
    if extra_lines:
        lines += ["", *extra_lines]
    return "\n".join(lines)


class CellInfoScreen(ModalScreen[None]):
    """Read-only info modal for a selected asset or legacy cell."""

    DEFAULT_CSS = """
    CellInfoScreen {
        align: center middle;
    }
    CellInfoScreen > Vertical {
        background: $panel;
        border: round $primary;
        padding: 1 2;
        width: 80;
        height: auto;
    }
    CellInfoScreen #cell-info-title {
        width: 100%;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    CellInfoScreen #cell-info-body {
        width: 100%;
    }
    CellInfoScreen #cell-info-footer {
        margin-top: 1;
        color: $secondary;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
        Binding("q", "dismiss_modal", "Close"),
        Binding("i", "dismiss_modal", "Close"),
    ]

    def __init__(self, *, title: str, body_markup: str) -> None:
        super().__init__()
        self._title = title
        self._body_markup = body_markup

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title, id="cell-info-title")
            yield Static(self._body_markup, id="cell-info-body", markup=True)
            yield Static("Esc / q / i  close", id="cell-info-footer")

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)
