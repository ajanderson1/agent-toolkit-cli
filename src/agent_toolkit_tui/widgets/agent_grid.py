"""Interactive DataTable for the TUI's agent tab.

Columns: AGENT ⓘ | <INTERACTIVE_HARNESSES...> | Source.

Mirrors skill_grid.py: per-harness columns, scope toggle, toggle-queue →
pending → apply. Pending key shape: (scope, harness_name, slug) — same
3-tuple as skill.

No State column (agents are installed real files, not git working trees).

CRITICAL: never name any method `_render_*` — it collides with Textual's
internal flag mechanism and produces "bool is not callable" from compose.
All glyph helpers are named `_cell_glyph`, `_harness_glyph`, `_rebuild`.
"""
from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.message import Message
from textual.widgets import DataTable

from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_tui.agent_state import INTERACTIVE_HARNESSES, AgentRow

_LINKED_GLYPH   = "[green]✔[/]"
_UNLINKED_GLYPH = "☐"
_PENDING_LINK   = "[yellow]+[/]"
_PENDING_UNLINK = "[yellow]-[/]"
_INFO_GLYPH     = "ⓘ"

Op = Literal["link", "unlink"]


class AgentGrid(Vertical):
    """One row per locked agent; interactive cells for INTERACTIVE_HARNESSES."""

    class PendingChanged(Message):
        """Posted whenever the pending toggle set changes.

        Carries the current pending count so the App can refresh the footer
        "Pending: N" label live as the user toggles cells.
        """

        def __init__(self, count: int) -> None:
            super().__init__()
            self.count = count

    DEFAULT_CSS = """
    AgentGrid { border: round $primary; }
    AgentGrid DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("space", "toggle_cell", "Toggle", priority=True),
        Binding("a", "toggle_column", "All/None", priority=True),
        Binding("i", "info", "Info", priority=True),
    ]

    def __init__(self, rows: list[AgentRow], *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._rows = sorted(rows, key=lambda r: r.slug)
        self._scope: Literal["global", "project"] = "global"
        # (scope, harness_name, slug) -> op
        self._pending: dict[tuple[str, str, str], Op] = {}

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def row_slugs(self) -> list[str]:
        return [r.slug for r in self._rows]

    def set_rows(self, rows: list[AgentRow]) -> None:
        self._rows = sorted(rows, key=lambda r: r.slug)
        self._pending.clear()
        try:
            table = self.query_one("#agent-table", DataTable)
        except Exception:
            return
        self._rebuild(table)

    def set_scope(self, scope: Literal["global", "project"]) -> None:
        self._scope = scope
        self._pending.clear()

    def pending_entries(self) -> dict[tuple[str, str, str], Op]:
        return dict(self._pending)

    def _notify_pending(self) -> None:
        """Announce the current pending count so the App can refresh the footer.

        Posted from the user-driven toggle paths. The App's own mutators
        (clear_pending / restore_pending / set_rows / set_scope) deliberately
        do NOT notify: their callers already set the footer line explicitly.
        """
        self.post_message(self.PendingChanged(len(self._pending)))

    def clear_pending(self) -> None:
        self._pending.clear()
        try:
            table = self.query_one("#agent-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def restore_pending(self, pending: dict[tuple[str, str, str], Op]) -> None:
        self._pending.update(pending)
        try:
            table = self.query_one("#agent-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        table: DataTable[str] = DataTable(
            id="agent-table", cursor_type="cell", zebra_stripes=True,
        )
        yield table

    def on_mount(self) -> None:
        try:
            table = self.query_one("#agent-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def action_toggle_cell(self) -> None:
        try:
            table = self.query_one("#agent-table", DataTable)
        except Exception:
            return
        self._toggle_at(table.cursor_coordinate)

    def action_info(self) -> None:
        """Open CellInfoScreen for the cell under the cursor."""
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen

        try:
            table = self.query_one("#agent-table", DataTable)
        except Exception:
            return
        coord = table.cursor_coordinate
        if coord.row >= len(self._rows):
            return
        row = self._rows[coord.row]

        if coord.column == 0:
            title = f"{row.slug} · agent"
            body = (
                f"Agent [b]{row.slug}[/]\n"
                f"Source: {row.source}\n"
                f"Ref:    {row.ref}"
            )
        else:
            harness = self._harness_for_column(coord.column)
            if harness is None:
                return
            cell = row.cells.get((harness, self._scope))
            scope_flag = "-g" if self._scope == "global" else "-p"
            title = f"{row.slug} · {harness} @ {self._scope}"
            pending = self._pending.get((self._scope, harness, row.slug))
            if pending == "link":
                body = (
                    "[yellow]Pending: install.[/]\n\n"
                    "Press [b]^s[/] to apply."
                )
            elif pending == "unlink":
                body = (
                    "[yellow]Pending: uninstall.[/]\n\n"
                    "Press [b]^s[/] to apply."
                )
            elif cell is None:
                body = f"Not available at {self._scope} scope."
            elif cell.linked:
                body = f"Installed.\nAgent {row.slug} is projected into {harness} @ {self._scope}."
            else:
                body = (
                    f"Not installed.\nPress [b]space[/] to queue install "
                    f"into {harness} @ {self._scope}.\n\n"
                    f"Or from the CLI:\n"
                    f"  [b]agent-toolkit-cli agent install {row.slug} "
                    f"{scope_flag} --harnesses {harness}[/]"
                )

        self.app.push_screen(CellInfoScreen(title=title, body_markup=body))

    def action_toggle_column(self) -> None:
        """Toggle all rows in the column under the cursor."""
        try:
            table = self.query_one("#agent-table", DataTable)
        except Exception:
            return
        col = table.cursor_coordinate.column
        harness = self._harness_for_column(col)
        if harness is None:
            return
        scope = self._scope
        # Determine target: if any cell in the column is effectively off → link all.
        any_off = False
        for r in self._rows:
            cell = r.cells.get((harness, scope))
            if cell is None:
                continue
            key = (scope, harness, r.slug)
            pending = self._pending.get(key)
            effective_linked = (
                (cell.linked and pending != "unlink") or pending == "link"
            )
            if not effective_linked:
                any_off = True
                break
        target_op: Op = "link" if any_off else "unlink"
        for r in self._rows:
            cell = r.cells.get((harness, scope))
            if cell is None:
                continue
            key = (scope, harness, r.slug)
            ground_matches = (
                (target_op == "link" and cell.linked)
                or (target_op == "unlink" and not cell.linked)
            )
            if ground_matches:
                self._pending.pop(key, None)
                continue
            self._pending[key] = target_op
        self._rebuild(table)
        self._notify_pending()

    def _toggle_at(self, coord: Coordinate) -> None:
        harness = self._harness_for_column(coord.column)
        if harness is None:
            return
        if coord.row >= len(self._rows):
            return
        row = self._rows[coord.row]
        cell = row.cells.get((harness, self._scope))
        if cell is None:
            # Cell not applicable at this scope — no-op.
            return
        key = (self._scope, harness, row.slug)
        if key in self._pending:
            del self._pending[key]
        else:
            self._pending[key] = "unlink" if cell.linked else "link"
        try:
            table = self.query_one("#agent-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass
        self._notify_pending()

    def _column_index(self, harness_name: str) -> int:
        """Return the table column index for a harness name. Layout: [0]=slug, [1..N]=harnesses, [N+1]=source."""
        try:
            return 1 + list(INTERACTIVE_HARNESSES).index(harness_name)
        except ValueError:
            return -1

    def _harness_for_column(self, col: int) -> str | None:
        """Return the harness name for a table column index, or None for slug/source cols."""
        if col < 1:
            return None
        idx = col - 1
        if 0 <= idx < len(INTERACTIVE_HARNESSES):
            return INTERACTIVE_HARNESSES[idx]
        return None

    def _rebuild(self, table: DataTable) -> None:
        """Rebuild the DataTable from current rows + pending. Never named _render_*."""
        saved = table.cursor_coordinate
        table.clear(columns=True)
        # Slug column — info glyph since `i` works on it.
        table.add_column(f"AGENT {_INFO_GLYPH}", width=22)
        # Per-harness columns.
        for harness in INTERACTIVE_HARNESSES:
            cfg = AGENTS.get(harness)
            display = cfg.display_name if cfg else harness
            table.add_column(f"{display} {_INFO_GLYPH}", width=14)
        # Source column — passive, no info popup.
        table.add_column("Source", width=30)

        for row in self._rows:
            cells: list[str] = [row.slug]
            for harness in INTERACTIVE_HARNESSES:
                cells.append(self._cell_glyph(row=row, harness=harness))
            cells.append(row.source)
            table.add_row(*cells, key=f"agent:{row.slug}")

        if self._rows:
            max_row = len(self._rows) - 1
            # Layout: slug + N harness cols + source.
            max_col = 1 + len(INTERACTIVE_HARNESSES)
            table.cursor_coordinate = Coordinate(
                row=min(saved.row, max_row),
                column=min(saved.column, max_col),
            )

    def _cell_glyph(self, *, row: AgentRow, harness: str) -> str:
        """Return the display glyph for a harness cell. Never named _render_*."""
        cell = row.cells.get((harness, self._scope))
        if cell is None:
            # Not applicable at this scope (e.g. dexto at project scope).
            return "[dim]—[/]"
        pending = self._pending.get((self._scope, harness, row.slug))
        if pending == "link":
            return _PENDING_LINK
        if pending == "unlink":
            return _PENDING_UNLINK
        return _LINKED_GLYPH if cell.linked else _UNLINKED_GLYPH

    def _harness_glyph(self, harness: str) -> str:
        """Return display name for a harness. Never named _render_*."""
        cfg = AGENTS.get(harness)
        return cfg.display_name if cfg else harness
