"""DataTable widget for the TUI's skill tab.

Renders SkillRow records. State column is color-coded.

NOTE: avoid method names beginning with `_render_*` — they collide with
Textual internal flags and produce 'bool not callable' errors from
compose() (see memory feedback_textual_render_methods.md).
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable

from agent_toolkit_tui.skill_state import SkillRow

_STATE_MARKUP = {
    "clean":   "[green]clean[/]",
    "dirty":   "[yellow]dirty[/]",
    "missing": "[red]missing[/]",
}


class SkillGrid(Vertical):
    """Skill tab grid: one row per locked skill."""

    DEFAULT_CSS = """
    SkillGrid { border: round $primary; }
    SkillGrid DataTable { height: 1fr; }
    """

    def __init__(self, rows: list[SkillRow], *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._rows = sorted(rows, key=lambda r: r.slug)

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def row_slugs(self) -> list[str]:
        return [r.slug for r in self._rows]

    def compose(self) -> ComposeResult:
        table: DataTable = DataTable(
            id="skill-table", cursor_type="row", zebra_stripes=True,
        )
        table.add_columns("slug", "source", "ref", "state")
        for r in self._rows:
            table.add_row(
                r.slug, r.source, r.ref, _STATE_MARKUP.get(r.state, r.state),
            )
        yield table
