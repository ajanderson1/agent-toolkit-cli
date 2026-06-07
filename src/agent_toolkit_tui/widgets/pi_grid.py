"""Interactive DataTable for the TUI's pi-extension tab.

Columns: EXTENSION | Pi (global) | Pi (project) | Origin | Source.

Both scope columns are always visible — no scope toggle (Pi has no per-harness
fan-out; five columns always fit comfortably).

`space` queues a link/unlink for the cell under the cursor.
`ctrl+s` Apply is handled by the App, which reads pending_entries().
`i` opens CellInfoScreen with per-cell context.

CRITICAL: never name any method `_render_*` — it collides with Textual's
internal flag mechanism and produces a "bool is not callable" error from
compose. All glyph helpers are named `_cell_glyph`, `_origin_glyph`, etc.

Untracked rows are non-interactive: toggling them is a no-op and their cells
display a dim glyph. They have no lock entry so there is nothing to act on.
"""
from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.message import Message
from textual.widgets import DataTable

from agent_toolkit_tui.pi_extension_state import PiExtensionRow
from agent_toolkit_tui.screens.cell_info import CellInfoScreen

Op = Literal["link", "unlink"]

_LOADED_GLYPH    = "[green]✔[/]"
_UNLOADED_GLYPH  = "☐"
_PENDING_LINK    = "[yellow]+[/]"
_PENDING_UNLINK  = "[yellow]-[/]"
_UNTRACKED_GLYPH = "[dim]—[/]"
_INFO_GLYPH      = "ⓘ"

_ORIGIN_MARKUP = {
    "store-owned": "[blue]store[/]",
    "npm":         "[cyan]npm[/]",
    "untracked":   "[dim]untracked[/]",
}

# Column indices (fixed, both scopes always shown).
_COL_EXTENSION = 0
_COL_GLOBAL    = 1
_COL_PROJECT   = 2
_COL_ORIGIN    = 3
_COL_SOURCE    = 4


class PiGrid(Vertical):
    """One row per Pi extension; interactive cells for global + project scopes."""

    class PendingChanged(Message):
        """Posted whenever the pending toggle set changes."""

        def __init__(self, count: int) -> None:
            super().__init__()
            self.count = count

    DEFAULT_CSS = """
    PiGrid { border: round $primary; }
    PiGrid DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("space", "toggle_cell", "Toggle", priority=True),
        Binding("i", "info", "Info", priority=True),
    ]

    def __init__(self, rows: list[PiExtensionRow], *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._rows: list[PiExtensionRow] = sorted(rows, key=lambda r: r.slug)
        # (scope: "global"|"project", slug) -> Op
        self._pending: dict[tuple[str, str], Op] = {}

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def row_slugs(self) -> list[str]:
        return [r.slug for r in self._rows]

    def set_rows(self, rows: list[PiExtensionRow]) -> None:
        self._rows = sorted(rows, key=lambda r: r.slug)
        self._pending.clear()
        try:
            table = self.query_one("#pi-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def pending_entries(self) -> dict[tuple[str, str], Op]:
        return dict(self._pending)

    def clear_pending(self) -> None:
        self._pending.clear()
        try:
            table = self.query_one("#pi-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def restore_pending(self, pending: dict[tuple[str, str], Op]) -> None:
        self._pending.update(pending)
        try:
            table = self.query_one("#pi-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def _notify_pending(self) -> None:
        self.post_message(self.PendingChanged(len(self._pending)))

    def compose(self) -> ComposeResult:
        table: DataTable[str] = DataTable(id="pi-table", cursor_type="cell", zebra_stripes=True)
        yield table

    def on_mount(self) -> None:
        try:
            table = self.query_one("#pi-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def action_toggle_cell(self) -> None:
        try:
            table = self.query_one("#pi-table", DataTable)
        except Exception:
            return
        self._toggle_at(table.cursor_coordinate)

    def action_info(self) -> None:
        """Open CellInfoScreen for the cell under the cursor."""
        try:
            table = self.query_one("#pi-table", DataTable)
        except Exception:
            return
        coord = table.cursor_coordinate
        if coord.row >= len(self._rows):
            return
        row = self._rows[coord.row]

        col = coord.column
        if col == _COL_EXTENSION:
            title = f"{row.slug} · extension"
            body = (
                f"Pi extension [b]{row.slug}[/]\n"
                f"Origin: {row.origin}\n"
                f"Source: {row.source}"
            )
            if row.origin == "store-owned":
                from agent_toolkit_cli.pi_extension_paths import library_pi_extension_path
                ext_dir = library_pi_extension_path(row.slug)
                body += f"\nStore path: {ext_dir}"
        elif col == _COL_GLOBAL:
            scope = "global"
            title = f"{row.slug} · Pi (global)"
            body = self._info_body(row=row, scope=scope)
        elif col == _COL_PROJECT:
            scope = "project"
            title = f"{row.slug} · Pi (project)"
            body = self._info_body(row=row, scope=scope)
        elif col == _COL_ORIGIN:
            title = f"{row.slug} · origin"
            body = (
                f"Origin: {row.origin}\n\n"
                f"[b]store-owned[/]: cloned into the agent-toolkit library;\n"
                f"  managed via pi-extension add/install/update.\n"
                f"[b]npm[/]: registry package in Pi settings.json packages[];\n"
                f"  managed via pi-extension install (scope toggle).\n"
                f"[b]untracked[/]: found in Pi's extensions/ dir but not in\n"
                f"  the kind lock. Use pi-extension import to adopt."
            )
        else:
            return

        self.app.push_screen(CellInfoScreen(title=title, body_markup=body))

    def _info_body(self, *, row: PiExtensionRow, scope: str) -> str:
        from pathlib import Path
        from agent_toolkit_cli.pi_extension_paths import (
            library_pi_extension_path,
            pi_extension_dir,
        )

        if row.origin == "untracked":
            return (
                f"[dim]Untracked extension.[/]\n\n"
                f"This extension is not in the kind lock and cannot be\n"
                f"toggled here. To adopt it, run:\n"
                f"  [b]agent-toolkit-cli pi-extension import {row.slug}[/]"
            )

        home = Path.home()
        project = Path.cwd() if scope == "project" else None
        pending = self._pending.get((scope, row.slug))
        loaded = row.global_cell.global_loaded if scope == "global" else row.project_cell.project_loaded

        if row.origin == "npm":
            if pending == "link":
                return (
                    f"[yellow]Pending: install (npm).[/]\n"
                    f"Will add {row.source} to packages[] @ {scope}.\n\n"
                    f"Press [b]^s[/] to apply."
                )
            if pending == "unlink":
                return (
                    f"[yellow]Pending: uninstall (npm).[/]\n"
                    f"Will remove {row.source} from packages[] @ {scope}.\n\n"
                    f"Press [b]^s[/] to apply."
                )
            if loaded:
                return f"Loaded (npm).\nPackage {row.source} is in packages[] @ {scope}."
            return (
                f"Not loaded (npm).\nPress [b]space[/] to queue install\n"
                f"(adds {row.source} to packages[] @ {scope})."
            )

        # store-owned
        if scope == "global":
            link = pi_extension_dir(row.slug, scope="global", home=home)
        else:
            link = pi_extension_dir(row.slug, scope="project", project=project)
        canonical = library_pi_extension_path(row.slug)

        if pending == "link":
            return (
                f"[yellow]Pending: install.[/]\n"
                f"{link} → {canonical}\n\n"
                f"Press [b]^s[/] to apply."
            )
        if pending == "unlink":
            return (
                f"[yellow]Pending: uninstall.[/]\n"
                f"{link}\n\n"
                f"Press [b]^s[/] to apply."
            )
        if loaded:
            return f"Loaded.\n{link} → {canonical}"
        return (
            f"Not loaded.\nPress [b]space[/] to queue install\n"
            f"({link} → {canonical})."
        )

    def _toggle_at(self, coord: Coordinate) -> None:
        if coord.row >= len(self._rows):
            return
        row = self._rows[coord.row]

        # Untracked rows are non-interactive — no lock entry to act on.
        if row.origin == "untracked":
            return

        scope: str | None = None
        if coord.column == _COL_GLOBAL:
            scope = "global"
        elif coord.column == _COL_PROJECT:
            scope = "project"
        else:
            return

        key = (scope, row.slug)
        if key in self._pending:
            del self._pending[key]
        else:
            loaded = (
                row.global_cell.global_loaded
                if scope == "global"
                else row.project_cell.project_loaded
            )
            self._pending[key] = "unlink" if loaded else "link"

        try:
            table = self.query_one("#pi-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass
        self._notify_pending()

    def _rebuild(self, table: DataTable) -> None:
        saved = table.cursor_coordinate
        # Preserve the viewport across clear() (#321): clear() resets scroll to
        # the top, so a toggle would jump the pane. Restore the offset below.
        # On the toggle path (cursor unchanged) the restored cursor stays in the
        # restored viewport, so Textual's deferred _scroll_cursor_into_view is a
        # no-op and the offset holds. See skill_grid._rebuild for the full note.
        saved_scroll = (table.scroll_x, table.scroll_y)
        table.clear(columns=True)
        table.add_column(f"EXTENSION {_INFO_GLYPH}", width=24)
        table.add_column(f"Pi (global) {_INFO_GLYPH}", width=14)
        table.add_column(f"Pi (project) {_INFO_GLYPH}", width=14)
        table.add_column("Origin", width=12)
        table.add_column("Source", width=30)

        for row in self._rows:
            cells = [
                row.slug,
                self._cell_glyph(row=row, scope="global"),
                self._cell_glyph(row=row, scope="project"),
                self._origin_glyph(row.origin),
                row.source,
            ]
            table.add_row(*cells, key=f"pi:{row.slug}")

        if self._rows:
            max_row = len(self._rows) - 1
            max_col = _COL_SOURCE
            table.cursor_coordinate = Coordinate(
                row=min(saved.row, max_row),
                column=min(saved.column, max_col),
            )
        # Pin the viewport back (clamped by Textual to the new content range).
        table.scroll_to(
            x=saved_scroll[0], y=saved_scroll[1], animate=False, force=True
        )

    def _cell_glyph(self, *, row: PiExtensionRow, scope: str) -> str:
        """Return the display glyph for a scope cell. Never named _render_*."""
        if row.origin == "untracked":
            return _UNTRACKED_GLYPH

        loaded = (
            row.global_cell.global_loaded
            if scope == "global"
            else row.project_cell.project_loaded
        )
        pending = self._pending.get((scope, row.slug))
        if pending == "link":
            return _PENDING_LINK
        if pending == "unlink":
            return _PENDING_UNLINK
        return _LOADED_GLYPH if loaded else _UNLOADED_GLYPH

    def _origin_glyph(self, origin: str) -> str:
        """Return styled markup for an origin label. Never named _render_*."""
        return _ORIGIN_MARKUP.get(origin, origin)
