"""Interactive DataTable for the TUI's pi-extension tab.

Columns: EXTENSION | Pi | Origin | Source.

One scope is visible at a time; the app's ctrl+g scope toggle flips it
app-wide (#349). The header carries no scope name — the ScopeToggle widget
communicates scope, and in project scope a 🌐 suffix marks rows that are
loaded globally (both match the other asset-type grids). set_scope() follows
the same contract as the other grids (sets scope, clears pending); pending
preservation across the toggle is orchestrated by the App, not the widget.

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
from textual.widgets import DataTable, Input
from textual.events import Resize
from rich.text import Text
from agent_toolkit_tui.widgets._support import adjust_source_column_width, current_source_column_width

from agent_toolkit_tui.display_names import asset_type_label, pi_extension_origin_label
from agent_toolkit_tui.pi_extension_state import PiExtensionRow
from agent_toolkit_tui.screens.cell_info import CellInfoScreen
from agent_toolkit_tui.widgets.filter_input import GridFilterInput

Op = Literal["link", "unlink"]

_LOADED_GLYPH    = "[green]✔[/]"
_UNLOADED_GLYPH  = "☐"
_PENDING_LINK    = "[yellow]+[/]"
_PENDING_UNLINK  = "[yellow]-[/]"
_UNTRACKED_GLYPH = "[dim]—[/]"
_INFO_GLYPH      = "ⓘ"
_GLOBAL_GLYPH    = "🌐"

_ORIGIN_MARKUP = {
    "store-owned": "[blue]library[/]",
    "untracked":   "[dim]untracked[/]",
}

# Column indices (single scope column; the active scope is self._scope).
_COL_EXTENSION = 0
_COL_SCOPE     = 1
_COL_ORIGIN    = 2
_COL_SOURCE    = 3


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
        self._scope: Literal["global", "project"] = "global"
        # (scope: "global"|"project", slug) -> Op
        self._pending: dict[tuple[str, str], Op] = {}
        self._filter: str = ""

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

    def set_scope(self, scope: Literal["global", "project"]) -> None:
        self._scope = scope
        self._pending.clear()
        # Snap the cursor to the single interactive scope column (same row).
        try:
            table = self.query_one("#pi-table", DataTable)
            table.cursor_coordinate = Coordinate(
                row=table.cursor_coordinate.row, column=_COL_SCOPE
            )
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

    def _project_install_blocked(self, *, row: PiExtensionRow, loaded: bool) -> bool:
        return self._scope == "project" and row.global_cell.global_loaded and not loaded

    def _notify_pending(self) -> None:
        self.post_message(self.PendingChanged(len(self._pending)))

    def compose(self) -> ComposeResult:
        yield GridFilterInput(table_selector="#pi-table", id="pi-filter")
        table: DataTable[str] = DataTable(id="pi-table", cursor_type="cell", zebra_stripes=True)
        yield table

    def set_filter(self, text: str) -> None:
        self._filter = text.strip().lower()
        try:
            table = self.query_one("#pi-table", DataTable)
        except Exception:
            return
        self._rebuild(table)

    def _visible_rows(self) -> list[PiExtensionRow]:
        if self._filter:
            return [row for row in self._rows if self._filter in row.slug.lower()]
        return list(self._rows)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "pi-filter":
            self.set_filter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "pi-filter":
            try:
                self.query_one("#pi-table", DataTable).focus()
            except Exception:
                pass

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
        visible = self._visible_rows()
        if coord.row >= len(visible):
            return
        row = visible[coord.row]

        col = coord.column
        if col == _COL_EXTENSION:
            title = f"{row.slug} · extension"
            body = self._extension_info_body(row)
        elif col == _COL_SCOPE:
            scope = self._scope
            title = f"{row.slug} · Pi ({scope})"
            body = self._info_body(row=row, scope=scope)
        elif col == _COL_ORIGIN:
            title = f"{row.slug} · origin"
            body = self._origin_info_body()
        else:
            return

        self.app.push_screen(CellInfoScreen(title=title, body_markup=body))

    def _extension_info_body(self, row: PiExtensionRow) -> str:
        body = (
            f"Pi extension [b]{row.slug}[/]\n"
            f"Origin: {self._origin_label(row)}\n"
            f"Source: {row.source}"
        )
        if row.origin == "store-owned":
            from agent_toolkit_cli.pi_extension_paths import library_pi_extension_path

            ext_dir = library_pi_extension_path(row.slug)
            body += f"\nLibrary path: {ext_dir}"
        return body

    def _origin_info_body(self) -> str:
        return (
            "Origin labels:\n\n"
            "[b]library-owned[/]: cloned into the agent-toolkit library;\n"
            "  managed via pi-extension add/install/update.\n"
            "[b]npm managed[/]: registry package in Pi settings.json packages[];\n"
            "  managed via pi-extension install (scope toggle).\n"
            "[b]npm unmanaged[/]: registry package Pi loads from settings.json,\n"
            "  but agent-toolkit did not add it; remove manually from packages[].\n"
            "[b]untracked[/]: found in Pi's extensions/ dir but not in\n"
            "  the asset-type lock. Use pi-extension import to adopt."
        )

    def _info_body(self, *, row: PiExtensionRow, scope: str) -> str:
        from pathlib import Path
        from agent_toolkit_cli.pi_extension_paths import (
            library_pi_extension_path,
            pi_extension_dir,
        )

        if row.origin == "untracked":
            return (
                f"[dim]Untracked extension.[/]\n\n"
                f"This extension is not in the asset-type lock and cannot be\n"
                f"toggled here. To adopt it, run:\n"
                f"  [b]agent-toolkit-cli pi-extension import {row.slug}[/]"
            )

        home = Path.home()
        project = Path.cwd() if scope == "project" else None
        pending = self._pending.get((scope, row.slug))
        loaded = row.global_cell.global_loaded if scope == "global" else row.project_cell.project_loaded

        if row.origin == "npm":
            if not row.managed:
                if scope == "global":
                    path = row.global_config_path or row.project_config_path or "Pi settings.json"
                    spec = row.global_package_spec or row.project_package_spec or row.source
                else:
                    path = row.project_config_path or row.global_config_path or "Pi settings.json"
                    spec = row.project_package_spec or row.global_package_spec or row.source
                return (
                    "[dim]unmanaged npm package.[/]\n\n"
                    "agent-toolkit-cli will not remove packages it did not add.\n"
                    f"To remove it manually, edit {path} and remove \"{spec}\" from packages[]."
                )
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
            if scope == "project" and row.global_cell.global_loaded:
                return (
                    f"Not loaded in project (npm).\n"
                    f"Already loaded globally as {row.source}.\n"
                    f"Project install is unavailable; uninstall globally first "
                    f"if this extension must be project-scoped."
                )
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
        if scope == "project" and row.global_cell.global_loaded:
            return (
                f"Not loaded in project.\n"
                f"Already loaded globally.\n"
                f"Project install is unavailable; uninstall globally first "
                f"if this extension must be project-scoped.\n"
                f"{link} → {canonical}"
            )
        return (
            f"Not loaded.\nPress [b]space[/] to queue install\n"
            f"({link} → {canonical})."
        )

    def _toggle_at(self, coord: Coordinate) -> None:
        visible = self._visible_rows()
        if coord.row >= len(visible):
            return
        row = visible[coord.row]

        # Untracked rows are non-interactive — no lock entry to act on.
        if row.origin == "untracked":
            return

        if row.origin == "npm" and not row.managed:
            try:
                self.app.notify(
                    "unmanaged npm package: remove manually from Pi settings.json packages[]",
                    severity="warning",
                )
            except Exception:
                pass
            return

        if coord.column != _COL_SCOPE:
            return
        scope = self._scope

        key = (scope, row.slug)
        if key in self._pending:
            del self._pending[key]
        else:
            loaded = (
                row.global_cell.global_loaded
                if scope == "global"
                else row.project_cell.project_loaded
            )
            if self._project_install_blocked(row=row, loaded=loaded):
                return
            self._pending[key] = "unlink" if loaded else "link"

        try:
            table = self.query_one("#pi-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass
        self._notify_pending()

    def on_resize(self, event: Resize) -> None:
        try:
            table = self.query_one("#pi-table", DataTable)
        except Exception:
            return

        fixed_width = 24 + 14 + 12
        adjust_source_column_width(table, event, fixed_width)

    def _rebuild(self, table: DataTable) -> None:
        saved = table.cursor_coordinate
        # Preserve the viewport across clear() (#321): clear() resets scroll to
        # the top, so a toggle would jump the pane. Restore the offset below.
        # On the toggle path (cursor unchanged) the restored cursor stays in the
        # restored viewport, so Textual's deferred _scroll_cursor_into_view is a
        # no-op and the offset holds. See skill_grid._rebuild for the full note.
        saved_scroll = (table.scroll_x, table.scroll_y)
        source_width = current_source_column_width(table)
        table.clear(columns=True)
        table.add_column(f"{asset_type_label('pi-extension')} {_INFO_GLYPH}", width=24)
        table.add_column(f"Pi {_INFO_GLYPH}", width=14)
        table.add_column("Origin", width=12)
        table.add_column("Source", width=source_width)

        visible = self._visible_rows()
        for row in visible:
            cells: list[str | Text] = [
                row.slug,
                self._cell_glyph(row=row, scope=self._scope),
                self._origin_glyph(row),
                Text(row.source, no_wrap=True, overflow="ellipsis"),
            ]
            table.add_row(*cells, key=f"pi:{row.slug}")

        if visible:
            max_row = len(visible) - 1
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
            base = _PENDING_LINK
        elif pending == "unlink":
            base = _PENDING_UNLINK
        else:
            base = _LOADED_GLYPH if loaded else _UNLOADED_GLYPH
        # In project scope, mark rows that are also loaded globally — same
        # indicator as the skill grid's global indicator (#349).
        if scope == "project" and row.global_cell.global_loaded:
            return f"{base} {_GLOBAL_GLYPH}"
        return base

    def _origin_label(self, row: PiExtensionRow) -> str:
        if row.origin == "npm":
            return "npm managed" if row.managed else "npm unmanaged"
        return pi_extension_origin_label(row.origin)

    def _origin_glyph(self, row: PiExtensionRow) -> str:
        """Return styled markup for an origin label. Never named _render_*."""
        if row.origin == "npm":
            return "[cyan]npm managed[/]" if row.managed else "[yellow]npm unmanaged[/]"
        return _ORIGIN_MARKUP.get(row.origin, pi_extension_origin_label(row.origin))
