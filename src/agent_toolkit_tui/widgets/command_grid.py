"""Interactive DataTable for the TUI's command tab.

Columns (#361/#360): AGENT ⓘ | Standard ⓘ | <non-covered main harnesses…> | State | Source.

Layout: [0]=slug, [1..N]=harnesses, [N+1]=state, [N+2]=source.

Mirrors skill_grid.py: per-harness columns, scope toggle, toggle-queue →
pending → apply. Pending key shape: (scope, harness_name, slug) — same
3-tuple as skill. The Standard column IS a harness column (the
.claude/commands slot is a real installable destination) — it toggles like
any other; `i` on it opens the registry-backed ColumnInfoModal listing
the covered harnesses for the active scope.

CRITICAL: never name any method `_render_*` — it collides with Textual's
internal flag mechanism and produces "bool is not callable" from compose.
All glyph helpers are named `_cell_glyph`, `_rebuild`.
"""
from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.message import Message
from textual.widgets import DataTable

from agent_toolkit_tui.command_state import INTERACTIVE_HARNESSES, CommandRow
from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal

_LINKED_GLYPH   = "[green]✔[/]"
_UNLINKED_GLYPH = "☐"
_PENDING_LINK   = "[yellow]+[/]"
_PENDING_UNLINK = "[yellow]-[/]"
_INFO_GLYPH     = "ⓘ"
_GLOBAL_GLYPH   = "🌐"

# Row-state badges (#360). `installed` renders as an em-dash to keep the
# common case quiet; `library` mirrors skill_grid's dim available state;
# `unlisted` gets a warning tint.
_STATE_MARKUP = {
    "installed": "[dim]—[/]",
    "library": "[dim]library[/]",
    "unlisted": "[yellow]unlisted[/]",
}

Op = Literal["link", "unlink"]


class CommandGrid(Vertical):
    """One row per locked command; interactive cells for INTERACTIVE_HARNESSES."""

    class PendingChanged(Message):
        """Posted whenever the pending toggle set changes.

        Carries the current pending count so the App can refresh the footer
        "Pending: N" label live as the user toggles cells.
        """

        def __init__(self, count: int) -> None:
            super().__init__()
            self.count = count

    DEFAULT_CSS = """
    CommandGrid { border: round $primary; }
    CommandGrid DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("space", "toggle_cell", "Toggle", priority=True),
        Binding("a", "toggle_column", "All/None", priority=True),
        Binding("i", "info", "Info", priority=True),
    ]

    def __init__(self, rows: list[CommandRow], *, id: str | None = None) -> None:
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

    def set_rows(self, rows: list[CommandRow]) -> None:
        self._rows = sorted(rows, key=lambda r: r.slug)
        self._pending.clear()
        try:
            table = self.query_one("#command-table", DataTable)
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
            table = self.query_one("#command-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def restore_pending(self, pending: dict[tuple[str, str, str], Op]) -> None:
        self._pending.update(pending)
        try:
            table = self.query_one("#command-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        table: DataTable[str] = DataTable(
            id="command-table", cursor_type="cell", zebra_stripes=True,
        )
        yield table

    def on_mount(self) -> None:
        try:
            table = self.query_one("#command-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def action_toggle_cell(self) -> None:
        try:
            table = self.query_one("#command-table", DataTable)
        except Exception:
            return
        self._toggle_at(table.cursor_coordinate)

    def action_info(self) -> None:
        """Route `i` by column. The standard column has registered ColumnInfo
        and opens ColumnInfoModal — the registry path mirroring
        instruction_grid (#351/#361). Everything else opens CellInfoScreen
        with the per-cell state."""
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen

        try:
            table = self.query_one("#command-table", DataTable)
        except Exception:
            return
        coord = table.cursor_coordinate
        key = self._column_key_for_index(coord.column)
        if key is not None:
            info = get_column_info(
                key, context=self._context_for(key=key, row_index=coord.row),
            )
            if info is not None:
                self.app.push_screen(ColumnInfoModal(info))
                return
        if coord.row >= len(self._rows):
            return
        row = self._rows[coord.row]

        if coord.column == 0:
            title = f"{row.slug} · command"
            body = (
                f"Command [b]{row.slug}[/]\n"
                f"Source: {row.source}\n"
                f"Ref:    {row.ref}\n"
                f"State:  {'—' if row.state == 'installed' else row.state}"
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
                body = f"Installed.\nCommand {row.slug} is projected into {harness} @ {self._scope}."
            else:
                body = (
                    f"Not installed.\nPress [b]space[/] to queue install "
                    f"into {harness} @ {self._scope}.\n\n"
                    f"Or from the CLI:\n"
                    f"  [b]agent-toolkit-cli command install {row.slug} "
                    f"{scope_flag} --harnesses {harness}[/]"
                )

        self.app.push_screen(CellInfoScreen(title=title, body_markup=body))

    def action_toggle_column(self) -> None:
        """Toggle all rows in the column under the cursor."""
        try:
            table = self.query_one("#command-table", DataTable)
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
            table = self.query_one("#command-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass
        self._notify_pending()

    def _column_index(self, harness_name: str) -> int:
        """Return the table column index for a harness name. Layout: [0]=slug, [1..N]=harnesses, [N+1]=state, [N+2]=source."""
        try:
            return 1 + list(INTERACTIVE_HARNESSES).index(harness_name)
        except ValueError:
            return -1

    def _harness_for_column(self, col: int) -> str | None:
        """Return the harness name for a table column index, or None for slug/state/source cols. Layout: [0]=slug, [1..N]=harnesses, [N+1]=state, [N+2]=source."""
        if col < 1:
            return None
        idx = col - 1
        if 0 <= idx < len(INTERACTIVE_HARNESSES):
            return INTERACTIVE_HARNESSES[idx]
        return None

    def _column_key_for_index(self, col: int) -> str | None:
        """Resolve a column index to a COLUMN_INFO registry key (#361).

        Only the standard column has registered ColumnInfo; harness/slug/
        source columns return None and fall through to CellInfoScreen.
        """
        if self._harness_for_column(col) == "standard":
            return "standard"
        return None

    def _context_for(self, *, key: str, row_index: int) -> dict | None:
        """Context for get_column_info(): the standard panel enumerates the
        native .claude/commands readers from the per-scope coverage SSOT (#361).

        At global scope the panel carries the devin note (devin reads the
        slot at project scope only, so it is absent from the global covered
        set); at project scope devin is simply covered and the note is gone.

        Also surfaces whether the focused row is installed globally so the
        modal can omit the 🌐 paragraph when it's not (#374) — mirrors
        skill_grid._context_for.
        """
        return None

    def _rebuild(self, table: DataTable) -> None:
        """Rebuild the DataTable from current rows + pending. Never named _render_*."""
        saved = table.cursor_coordinate
        # Preserve the viewport across clear() (#321): clear() resets scroll to
        # the top, so a toggle would jump the pane. Restore the offset below.
        # On the toggle path (cursor unchanged) the restored cursor stays in the
        # restored viewport, so Textual's deferred _scroll_cursor_into_view is a
        # no-op and the offset holds. See skill_grid._rebuild for the full note.
        saved_scroll = (table.scroll_x, table.scroll_y)
        table.clear(columns=True)
        # Slug column — info glyph since `i` works on it.
        table.add_column(f"COMMAND {_INFO_GLYPH}", width=22)
        # Per-harness columns. "standard" is the .claude/commands slot (#361),
        # not a catalog harness — label it explicitly (same special-case as
        # skill_grid). The Standard column leads; everything after it is
        # implicitly non-standard.
        for harness in INTERACTIVE_HARNESSES:
            table.add_column(f"{harness} {_INFO_GLYPH}", width=14)
        # State column — shows installed/library/unlisted (#360).
        table.add_column("State", width=10)
        # Source column — passive, no info popup.
        table.add_column("Source", width=30)

        for row in self._rows:
            cells: list[str] = [row.slug]
            for harness in INTERACTIVE_HARNESSES:
                cells.append(self._cell_glyph(row=row, harness=harness))
            cells.append(_STATE_MARKUP.get(row.state, row.state))
            cells.append(row.source)
            table.add_row(*cells, key=f"command:{row.slug}")

        if self._rows:
            max_row = len(self._rows) - 1
            # Layout: slug + N harness cols + state + source.
            max_col = 2 + len(INTERACTIVE_HARNESSES)
            table.cursor_coordinate = Coordinate(
                row=min(saved.row, max_row),
                column=min(saved.column, max_col),
            )
        # Pin the viewport back (clamped by Textual to the new content range).
        table.scroll_to(
            x=saved_scroll[0], y=saved_scroll[1], animate=False, force=True
        )

    def _cell_glyph(self, *, row: CommandRow, harness: str) -> str:
        """Return the display glyph for a harness cell. Never named _render_*."""
        cell = row.cells.get((harness, self._scope))
        if cell is None:
            # Not applicable at this scope (e.g. dexto at project scope).
            base = "[dim]—[/]"
        else:
            pending = self._pending.get((self._scope, harness, row.slug))
            if pending == "link":
                base = _PENDING_LINK
            elif pending == "unlink":
                base = _PENDING_UNLINK
            else:
                base = _LINKED_GLYPH if cell.linked else _UNLINKED_GLYPH
        # In project scope, mark cells whose harness slot is also linked
        # globally — same indicator as skill_grid (#188) / pi_grid (#349).
        # CommandCell has no drift/stray/skipped states, so linked is the
        # whole gate (#374). Appends to any base, including the
        # not-applicable em-dash.
        if self._scope == "project":
            global_cell = row.cells.get((harness, "global"))
            if global_cell is not None and global_cell.linked:
                return f"{base} {_GLOBAL_GLYPH}"
        return base
