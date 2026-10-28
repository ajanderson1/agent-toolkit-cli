"""CellInfoScreen — modal that renders state-specific info for a SkillGrid cell."""
from __future__ import annotations

from rich.text import Text

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from rich.markup import escape

from agent_toolkit_tui.info_presentation import (
    InfoSection,
    compact_detail,
    detail_sections,
    facts,
    sections_markup,
)


def asset_info_body(
    *,
    asset_label: str,
    slug: str,
    description: str | None,
    description_location: str,
    source: str,
    origin: str,
    ref: str | None,
    state: str,
    scope: str,
    extra_lines: list[str] | None = None,
    show_ref: bool = True,
) -> str:
    """Render the shared, progressively disclosed asset panel body for every grid."""

    del slug, description_location  # Identity is the title; empty sections are omitted.
    source_summary, full_source = compact_detail(source, limit=42)
    ref_summary, full_ref = compact_detail(ref or "—", limit=42) if show_ref else ("", None)
    sections = [
        InfoSection(
            "At a glance",
            facts(
                ("Type", asset_label),
                ("Origin", origin),
                ("State", state),
                ("Scope", scope),
            ),
        ),
    ]
    if description and description.strip():
        sections.append(InfoSection("Description", (escape(description.strip()),)))
    sections.append(
        InfoSection(
            "Source & location",
            facts(*([( "Source", source_summary), ("Ref", ref_summary)] if show_ref else [("Source", source_summary)])),
        )
    )
    details = list(detail_sections(extra_lines or [], source=source))
    full_facts = []
    if full_source:
        full_facts.append(("Full source", full_source))
    if full_ref:
        full_facts.append(("Full ref", full_ref))
    if full_facts:
        if details and details[-1].title == "Technical details":
            technical = details[-1]
            details[-1] = InfoSection(
                technical.title,
                (*technical.lines, *facts(*full_facts)),
                technical.variant,
            )
        else:
            details.append(InfoSection("Technical details", facts(*full_facts)))
    sections.extend(details)
    return sections_markup(sections)


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
        max-width: 95%;
        height: auto;
        max-height: 80%;
    }
    CellInfoScreen > Vertical > VerticalScroll {
        width: 100%;
        height: 1fr;
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
        color: $text;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
        Binding("q", "dismiss_modal", "Close"),
        Binding("i", "dismiss_modal", "Close"),
        Binding("up", "scroll_up", show=False),
        Binding("down", "scroll_down", show=False),
        Binding("pageup", "scroll_page_up", show=False),
        Binding("pagedown", "scroll_page_down", show=False),
    ]

    def __init__(self, *, title: str, body_markup: str) -> None:
        super().__init__()
        self._title = title
        self._body_markup = body_markup

    def compose(self) -> ComposeResult:
        with Vertical():
            with VerticalScroll():
                yield Label(self._title, id="cell-info-title")
                # Info producers emit Rich markup. Parse it with Rich rather than
                # Textual's separate markup parser so Rich.escape preserves literal
                # backslash runs and bracket-like paths exactly as documented.
                yield Static(Text.from_markup(self._body_markup), id="cell-info-body")
            yield Static("↑/↓ or PgUp/PgDn scroll · Esc / q / i close", id="cell-info-footer")

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def action_scroll_up(self) -> None:
        self.query_one(VerticalScroll).scroll_relative(y=-1, animate=False)

    def action_scroll_down(self) -> None:
        self.query_one(VerticalScroll).scroll_relative(y=1, animate=False)

    def action_scroll_page_up(self) -> None:
        self.query_one(VerticalScroll).scroll_relative(y=-self.size.height + 3, animate=False)

    def action_scroll_page_down(self) -> None:
        self.query_one(VerticalScroll).scroll_relative(y=self.size.height - 3, animate=False)
