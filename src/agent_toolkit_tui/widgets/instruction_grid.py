"""Interactive DataTable for the TUI's instruction tab.

Columns: INSTRUCTION ⓘ (general — canonical AGENTS.md state) | Claude Code ⓘ |
         Gemini CLI ⓘ | Source.

Both scope rows are always shown (one row per scope with a lock entry) — no
scope toggle. The grid mirrors pi_grid.py's two-scope-no-toggle shape.

`space` queues a link/unlink for the cell under the cursor.
`ctrl+s` Apply is handled by the App, which reads pending_entries().

Pending key shape: (scope, harness, slug) — same 3-tuple as skill/agent.

CRITICAL: never name any method `_render_*` — it collides with Textual's
internal flag mechanism and produces a "bool is not callable" error from
compose. All glyph helpers are named `_cell_glyph`, `_rebuild`.

Not-applicable cells render a muted glyph (·) and are not toggleable.
"""
from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.message import Message
from textual.widgets import DataTable

from agent_toolkit_tui.instruction_state import INTERACTIVE_HARNESSES, InstructionRow

_LINKED_GLYPH     = "[green]✔[/]"
_UNLINKED_GLYPH   = "☐"
_PENDING_LINK     = "[yellow]+[/]"
_PENDING_UNLINK   = "[yellow]-[/]"
_NA_GLYPH         = "[dim]·[/]"
_INFO_GLYPH       = "ⓘ"

# Column index constants (fixed — both scopes always shown).
_COL_INSTRUCTION = 0   # general: canonical AGENTS.md present
_COL_CLAUDE_CODE = 1   # claude-code harness cell
_COL_GEMINI_CLI  = 2   # gemini-cli harness cell
_COL_SOURCE      = 3   # passive source column

# Map harness name → fixed column index (1-based after INSTRUCTION col).
_HARNESS_COL: dict[str, int] = {
    harness: idx + 1 for idx, harness in enumerate(INTERACTIVE_HARNESSES)
}

# Display names for the harness columns.
_HARNESS_DISPLAY: dict[str, str] = {
    "claude-code": "Claude Code",
    "gemini-cli":  "Gemini CLI",
}

Op = Literal["link", "unlink"]


class InstructionGrid(Vertical):
    """One row per scope (global / project) with entries; instruction kind."""

    class PendingChanged(Message):
        """Posted whenever the pending toggle set changes.

        Carries the current pending count so the App can refresh the footer
        "Pending: N" label live as the user toggles cells.
        """

        def __init__(self, count: int) -> None:
            super().__init__()
            self.count = count

    DEFAULT_CSS = """
    InstructionGrid { border: round $primary; }
    InstructionGrid DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("space", "toggle_cell", "Toggle", priority=True),
        Binding("i", "info", "Info", priority=True),
    ]

    def __init__(self, rows: list[InstructionRow], *, id: str | None = None) -> None:
        super().__init__(id=id)
        # Ordered: global first, project second — matches build_instruction_rows.
        self._rows: list[InstructionRow] = sorted(
            rows, key=lambda r: (0 if r.scope == "global" else 1)
        )
        # (scope, harness, slug) -> Op — same key shape as skill/agent.
        self._pending: dict[tuple[str, str, str], Op] = {}

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def row_slugs(self) -> list[str]:
        return [r.slug for r in self._rows]

    def set_rows(self, rows: list[InstructionRow]) -> None:
        self._rows = sorted(rows, key=lambda r: (0 if r.scope == "global" else 1))
        self._pending.clear()
        try:
            table = self.query_one("#instruction-table", DataTable)
        except Exception:
            return
        self._rebuild(table)

    def pending_entries(self) -> dict[tuple[str, str, str], Op]:
        return dict(self._pending)

    def clear_pending(self) -> None:
        self._pending.clear()
        try:
            table = self.query_one("#instruction-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def restore_pending(self, pending: dict[tuple[str, str, str], Op]) -> None:
        self._pending.update(pending)
        try:
            table = self.query_one("#instruction-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def _notify_pending(self) -> None:
        """Announce the current pending count so the App can refresh the footer.

        Posted from the user-driven toggle paths only. Callers that mutate
        state directly (clear_pending / restore_pending / set_rows) do NOT
        notify — their callers set the footer label explicitly.
        """
        self.post_message(self.PendingChanged(len(self._pending)))

    def compose(self) -> ComposeResult:
        table: DataTable[str] = DataTable(
            id="instruction-table", cursor_type="cell", zebra_stripes=True,
        )
        yield table

    def on_mount(self) -> None:
        try:
            table = self.query_one("#instruction-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def action_toggle_cell(self) -> None:
        try:
            table = self.query_one("#instruction-table", DataTable)
        except Exception:
            return
        self._toggle_at(table.cursor_coordinate)

    def action_info(self) -> None:
        """Open CellInfoScreen for the cell under the cursor."""
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen

        try:
            table = self.query_one("#instruction-table", DataTable)
        except Exception:
            return
        coord = table.cursor_coordinate
        if coord.row >= len(self._rows):
            return
        row = self._rows[coord.row]

        col = coord.column
        if col == _COL_INSTRUCTION:
            title = f"AGENTS.md · instruction ({row.scope})"
            body = (
                f"Canonical [b]AGENTS.md[/] — {row.scope} scope.\n"
                f"Present: {'yes' if row.general_linked else 'no'}"
            )
        elif col == _COL_SOURCE:
            title = f"Source · {row.scope}"
            body = f"Source: {row.slug}"
        else:
            harness = self._harness_for_column(col)
            if harness is None:
                return
            cell = row.cells.get(harness)
            pending = self._pending.get((row.scope, harness, row.slug))
            title = f"{row.slug} · {harness} @ {row.scope}"
            if not cell or not cell.applicable:
                body = f"Not available at {row.scope} scope."
            elif pending == "link":
                body = "[yellow]Pending: install.[/]\n\nPress [b]^s[/] to apply."
            elif pending == "unlink":
                body = "[yellow]Pending: uninstall.[/]\n\nPress [b]^s[/] to apply."
            elif cell.linked:
                body = (
                    f"Installed.\n{row.slug} pointer is active for {harness} @ {row.scope}."
                )
            else:
                body = (
                    f"Not installed.\nPress [b]space[/] to queue install "
                    f"into {harness} @ {row.scope}."
                )

        self.app.push_screen(CellInfoScreen(title=title, body_markup=body))

    def _toggle_at(self, coord: Coordinate) -> None:
        harness = self._harness_for_column(coord.column)
        if harness is None:
            # Column 0 (INSTRUCTION/general) and source are not toggleable.
            return
        if coord.row >= len(self._rows):
            return
        row = self._rows[coord.row]
        cell = row.cells.get(harness)
        if cell is None or not cell.applicable:
            # Not applicable at this scope — no-op.
            return
        key = (row.scope, harness, row.slug)
        if key in self._pending:
            del self._pending[key]
        else:
            self._pending[key] = "unlink" if cell.linked else "link"
        try:
            table = self.query_one("#instruction-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass
        self._notify_pending()

    def _harness_for_column(self, col: int) -> str | None:
        """Return the harness name for a table column index, or None for non-harness cols."""
        for harness, col_idx in _HARNESS_COL.items():
            if col_idx == col:
                return harness
        return None

    def _rebuild(self, table: DataTable) -> None:
        """Rebuild the DataTable from current rows + pending. Never named _render_*."""
        saved = table.cursor_coordinate
        table.clear(columns=True)
        # General column — canonical AGENTS.md install indicator.
        table.add_column(f"INSTRUCTION {_INFO_GLYPH}", width=16)
        # Per-harness columns.
        for harness in INTERACTIVE_HARNESSES:
            display = _HARNESS_DISPLAY.get(harness, harness)
            table.add_column(f"{display} {_INFO_GLYPH}", width=14)
        # Source column — passive.
        table.add_column("Source", width=14)

        for row in self._rows:
            general_glyph = _LINKED_GLYPH if row.general_linked else _UNLINKED_GLYPH
            cells_display: list[str] = [f"{general_glyph} {row.scope}"]
            for harness in INTERACTIVE_HARNESSES:
                cells_display.append(self._cell_glyph(row=row, harness=harness))
            cells_display.append(row.slug)
            table.add_row(*cells_display, key=f"instr:{row.scope}")

        if self._rows:
            max_row = len(self._rows) - 1
            max_col = _COL_SOURCE
            table.cursor_coordinate = Coordinate(
                row=min(saved.row, max_row),
                column=min(saved.column, max_col),
            )

    def _cell_glyph(self, *, row: InstructionRow, harness: str) -> str:
        """Return the display glyph for a harness cell. Never named _render_*."""
        cell = row.cells.get(harness)
        if cell is None or not cell.applicable:
            return _NA_GLYPH
        pending = self._pending.get((row.scope, harness, row.slug))
        if pending == "link":
            return _PENDING_LINK
        if pending == "unlink":
            return _PENDING_UNLINK
        return _LINKED_GLYPH if cell.linked else _UNLINKED_GLYPH
