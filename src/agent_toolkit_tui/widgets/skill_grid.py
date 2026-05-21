"""Interactive DataTable for the TUI's skill tab.

Columns: slug | claude-code | pi | state.

`space` toggles a cell (queues link/unlink in `_pending`).
`a` toggles a column.
`^s` Apply is handled by the App, which reads pending_entries().

The long tail of agents is managed via the CLI; the TUI grid only shows
the interactive shortlist (claude-code + pi).
"""
from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillRow

_STATE_MARKUP = {
    "clean":   "[green]clean[/]",
    "dirty":   "[yellow]dirty[/]",
    "missing": "[red]missing[/]",
    "copy":    "[blue]copy[/]",
    # "library" = in the library, not yet installed in this project. Normal
    # pre-install state. Rendered dim so it doesn't look alarming.
    "library": "[dim]library[/]",
}

_LINKED_GLYPH   = "[green]✔[/]"
_UNLINKED_GLYPH = "☐"
_PENDING_LINK   = "[yellow]+[/]"
_PENDING_UNLINK = "[yellow]-[/]"
_DRIFT_GLYPH    = "[red]![/]"
_SKIPPED_GLYPH  = "[dim]●[/]"  # canonical-only, no symlink needed

Op = Literal["link", "unlink"]


class SkillGrid(Vertical):
    """One row per locked skill; interactive cells for INTERACTIVE_AGENTS."""

    DEFAULT_CSS = """
    SkillGrid { border: round $primary; }
    SkillGrid DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("space", "toggle_cell", "Toggle", priority=True),
        Binding("a", "toggle_column", "All/None", priority=True),
    ]

    def __init__(self, rows: list[SkillRow], *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._rows = sorted(rows, key=lambda r: r.slug)
        self._scope: Literal["global", "project"] = "global"
        # (scope, agent_name, slug) -> op
        self._pending: dict[tuple[str, str, str], Op] = {}

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def row_slugs(self) -> list[str]:
        return [r.slug for r in self._rows]

    def set_rows(self, rows: list[SkillRow]) -> None:
        self._rows = sorted(rows, key=lambda r: r.slug)
        self._pending.clear()
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        self._rebuild(table)

    def set_scope(self, scope: Literal["global", "project"]) -> None:
        self._scope = scope
        self._pending.clear()

    def pending_entries(self) -> dict[tuple[str, str, str], Op]:
        return dict(self._pending)

    def clear_pending(self) -> None:
        self._pending.clear()
        try:
            table = self.query_one("#skill-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def restore_pending(self, pending: dict[tuple[str, str, str], Op]) -> None:
        self._pending.update(pending)
        try:
            table = self.query_one("#skill-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def cursor_to_cell(self, *, row_slug: str, agent_name: str) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        col_idx = self._column_index(agent_name)
        try:
            row_idx = self.row_slugs.index(row_slug)
        except ValueError:
            return
        table.cursor_coordinate = Coordinate(row=row_idx, column=col_idx)

    def compose(self) -> ComposeResult:
        table = DataTable(id="skill-table", cursor_type="cell", zebra_stripes=True)
        yield table

    def on_mount(self) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def action_toggle_cell(self) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        self._toggle_at(table.cursor_coordinate)

    def action_toggle_column(self) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        col = table.cursor_coordinate.column
        agent = self._agent_for_column(col)
        if agent is None:
            return
        scope = self._scope
        any_off = False
        for r in self._rows:
            cell = r.cells.get((agent, scope))
            if cell is None or cell.skipped:
                continue
            key = (scope, agent, r.slug)
            pending = self._pending.get(key)
            effective_linked = (
                (cell.linked and pending != "unlink") or pending == "link"
            )
            if not effective_linked:
                any_off = True
                break
        target_op: Op = "link" if any_off else "unlink"
        for r in self._rows:
            cell = r.cells.get((agent, scope))
            if cell is None or cell.skipped:
                continue
            key = (scope, agent, r.slug)
            ground_matches = (
                (target_op == "link" and cell.linked)
                or (target_op == "unlink" and not cell.linked)
            )
            if ground_matches:
                self._pending.pop(key, None)
                continue
            self._pending[key] = target_op
        self._rebuild(table)

    def _toggle_at(self, coord: Coordinate) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        agent = self._agent_for_column(coord.column)
        if agent is None:
            return
        if coord.row >= len(self._rows):
            return
        row = self._rows[coord.row]
        cell = row.cells.get((agent, self._scope))
        if cell is None or cell.skipped:
            return
        # Refuse destructive project-scope universal unlinks from the TUI.
        # Removing the project canonical (<project>/.agents/skills/<slug>/)
        # is a destructive operation that should be done explicitly via
        # `skill remove --scope project`, not from a cell click.
        # TODO: surface a user-visible message here (e.g. self.app.notify())
        # once a notify pattern is established for SkillGrid.
        if agent == "universal" and self._scope == "project" and cell.linked:
            return
        key = (self._scope, agent, row.slug)
        if key in self._pending:
            del self._pending[key]
        else:
            self._pending[key] = "unlink" if cell.linked else "link"
        self._rebuild(table)

    def _column_index(self, agent_name: str) -> int:
        # Layout: [0]=slug, [1..N]=INTERACTIVE_AGENTS, [N+1]=state
        try:
            return 1 + list(INTERACTIVE_AGENTS).index(agent_name)
        except ValueError:
            return -1

    def _agent_for_column(self, col: int) -> str | None:
        if col == 0:
            return None
        idx = col - 1
        if 0 <= idx < len(INTERACTIVE_AGENTS):
            return INTERACTIVE_AGENTS[idx]
        return None

    def _rebuild(self, table: DataTable) -> None:
        saved = table.cursor_coordinate
        table.clear(columns=True)
        table.add_column("slug", width=20)
        for agent in INTERACTIVE_AGENTS:
            # Use "universal" verbatim for the bundle column (lowercase, per spec).
            # Other agents use their catalog display_name.
            label = "universal" if agent == "universal" else AGENTS[agent].display_name
            table.add_column(label, width=14)
        table.add_column("state", width=10)
        for row in self._rows:
            cells: list[str] = [row.slug]
            for agent in INTERACTIVE_AGENTS:
                cells.append(self._cell_glyph(row=row, agent=agent))
            cells.append(_STATE_MARKUP.get(row.state, row.state))
            table.add_row(*cells, key=f"skill:{row.slug}")
        if self._rows:
            max_row = len(self._rows) - 1
            max_col = 1 + len(INTERACTIVE_AGENTS)
            table.cursor_coordinate = Coordinate(
                row=min(saved.row, max_row),
                column=min(saved.column, max_col),
            )

    def _cell_glyph(self, *, row: SkillRow, agent: str) -> str:
        cell = row.cells.get((agent, self._scope))
        if cell is None:
            return " "
        if cell.skipped:
            return _SKIPPED_GLYPH
        pending = self._pending.get((self._scope, agent, row.slug))
        if pending == "link":
            return _PENDING_LINK
        if pending == "unlink":
            return _PENDING_UNLINK
        if cell.drift:
            return _DRIFT_GLYPH
        return _LINKED_GLYPH if cell.linked else _UNLINKED_GLYPH
