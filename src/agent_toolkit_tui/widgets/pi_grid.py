"""Interactive DataTable for the TUI's pi-extension tab.

Columns: Pi Extension | Pi ⓘ | Origin ⓘ | Source.

One scope is visible at a time; the app's ctrl+g scope toggle flips it
app-wide (#349). The header carries no scope name — the ScopeToggle widget
communicates scope, and in project scope a 🌐 suffix marks rows that are
loaded globally (both match the other asset-type grids). set_scope() follows
the same contract as the other grids (sets scope, clears pending); pending
preservation across the toggle is orchestrated by the App, not the widget.

`space` queues a link/unlink for the cell under the cursor.
`ctrl+s` Apply is handled by the App, which reads pending_entries().
Clicking a glyphed header explains the column; `i` always explains the
selected extension.

CRITICAL: never name any method `_render_*` — it collides with Textual's
internal flag mechanism and produces a "bool is not callable" error from
compose. All glyph helpers are named `_cell_glyph`, `_origin_glyph`, etc.

Untracked rows are non-interactive: toggling them is a no-op and their cells
display a dim glyph. They have no lock entry so there is nothing to act on.
"""
from __future__ import annotations

from typing import Literal

from rich.markup import escape

from agent_toolkit_tui.asset_info import library_info, local_path_info

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.events import Resize
from textual.message import Message
from textual.widgets import DataTable, Input
from textual.events import Resize
from rich.text import Text
from agent_toolkit_tui.widgets._support import current_source_column_width

from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.display_names import asset_type_label, pi_extension_origin_label
from agent_toolkit_tui.widgets._support import (
    adjust_source_column_width,
    set_source_column_width,
)
from agent_toolkit_tui.pi_extension_state import PiExtensionRow
from agent_toolkit_tui.screens.cell_info import CellInfoScreen
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal
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
    "untracked":   "[dim]local[/]",
    "local-package": "[dim]local[/]",
}

# Column indices (single scope column; the active scope is self._scope).
_COL_EXTENSION = 0
_COL_SCOPE     = 1
_COL_ORIGIN    = 2
_COL_SOURCE    = 3

_DEFAULT_EXTENSION_WIDTH = 24
_MIN_EXTENSION_WIDTH = 10
_MIN_SOURCE_WIDTH = 10
_SCOPE_COLUMN_WIDTH = 14
_ORIGIN_COLUMN_WIDTH = 12
_FIXED_COLUMN_WIDTH = 24 + 14 + 12


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

    def on_resize(self, event: Resize) -> None:
        try:
            table = self.query_one("#pi-table", DataTable)
        except Exception:
            return
        adjust_source_column_width(table, event, _FIXED_COLUMN_WIDTH)

    def action_toggle_cell(self) -> None:
        try:
            table = self.query_one("#pi-table", DataTable)
        except Exception:
            return
        self._toggle_at(table.cursor_coordinate)

    def action_info(self) -> None:
        """Open the selected Pi extension's asset panel, regardless of column."""
        try:
            table = self.query_one("#pi-table", DataTable)
        except Exception:
            return
        visible = self._visible_rows()
        if table.cursor_coordinate.row >= len(visible):
            return
        row = visible[table.cursor_coordinate.row]
        state = "Linked" if row.origin == "store-owned" else "Enabled"
        self.app.push_screen(
            CellInfoScreen(
                title=f"{row.slug} · {asset_type_label('pi-extension')}",
                body_markup="\n".join([
                    f"Source: {escape(row.source)}",
                    "",
                    f"{state} globally: {'Yes' if row.global_cell.global_loaded else 'No'}",
                    f"{state} for this project: {'Yes' if row.project_cell.project_loaded else 'No'}",
                    "",
                    self._info_body(row=row, scope=self._scope),
                ]),
            )
        )

    def _column_key_for_index(self, col: int) -> str | None:
        """Resolve every explainable header to its registry key (#479 R2)."""
        if col == _COL_SCOPE:
            return "pi"
        if col == _COL_ORIGIN:
            return "origin"
        return None

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Click a glyphed header to explain that column (#479 R1)."""
        key = self._column_key_for_index(event.column_index)
        if key is None:
            return
        self.app.push_screen(
            ColumnInfoModal(
                get_column_info(
                    key,
                    asset_type="pi-extension",
                    context={"scope": self._scope},
                )
            )
        )

    def _extension_info_body(self, row: PiExtensionRow) -> str:
        if row.origin == "store-owned":
            from agent_toolkit_cli.pi_extension_paths import library_pi_extension_path

            return "\n".join(library_info(library_pi_extension_path(row.slug)))
        return ""

    def _origin_info_body(self) -> str:
        info = get_column_info("origin", asset_type="pi-extension", context={"scope": self._scope})
        return "\n".join(info.lines)

    def _info_body(self, *, row: PiExtensionRow, scope: str) -> str:
        sections = [self._extension_info_body(row), self._scope_info_body(row=row, scope=scope)]
        if row.origin == "npm":
            from shlex import join

            removal_scope = scope
            if scope == "project" and not row.project_package_spec and row.global_package_spec:
                removal_scope = "global"
            elif scope == "global" and not row.global_package_spec and row.project_package_spec:
                removal_scope = "project"
            spec = (
                row.global_package_spec if removal_scope == "global" else row.project_package_spec
            ) or row.source
            command = join(["pi", "uninstall", spec] + (["-l"] if removal_scope == "project" else []))
            removal = (
                f"Remove with Pi: {escape(command)}\n"
                "Removes package files and the Pi settings reference.\n"
            )
            removal += (
                "Run in this project's directory."
                if removal_scope == "project" else "Uses global Pi settings."
            )
            if row.managed:
                removal += "\nToolkit registration is kept."
            sections.append(removal)
        return "\n\n".join(section for section in sections if section)

    def _scope_info_body(self, *, row: PiExtensionRow, scope: str) -> str:
        from pathlib import Path
        from agent_toolkit_cli.pi_extension_paths import (
            pi_extension_dir,
        )

        if row.origin == "untracked":
            # Locate the already-discovered slug's actual loose file/directory.
            details: list[str] = []
            for location in (scope, "global" if scope == "project" else "project"):
                base = pi_extension_dir(
                    row.slug, scope=location, home=Path.home(),
                    project=Path.cwd() if location == "project" else None,
                )
                for path in (base, base.with_name(base.name + ".ts"), base.with_name(base.name + ".js")):
                    if path.exists() or path.is_symlink():
                        details += [f"Location ({location}):", *local_path_info(path), ""]
            return "\n".join(details) or "Local files are no longer present in either scope."

        if row.origin == "local-package":
            path = (
                row.global_config_path
                if scope == "global"
                else row.project_config_path
            ) or row.global_config_path or row.project_config_path or "Pi settings.json"
            spec = (
                row.global_package_spec
                if scope == "global"
                else row.project_package_spec
            ) or row.source
            candidate = Path(spec).expanduser()
            if not candidate.is_absolute():
                candidate = Path(path).parent / candidate
            return escape(
                f"Source path: {candidate}\n"
                "Existing local filesystem package; files are not moved or registered.\n"
                "No TUI enable/disable or deletion; edit/update the local files directly.\n"
                f"Manual removal: edit {path} and remove the packages[] entry\n"
                f"whose source is {spec!r} (or the matching string entry).\n"
                "This removes only the settings reference; it does not delete package files.\n"
                "Removing a reference does not unload an already-running session."
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
                    "Toolkit did not register this npm reference; toggles are unavailable.\n"
                    + escape(f"Manual removal: edit {path} and remove the packages[] entry "
                             f"whose source is {spec!r} (or the matching string entry).\n"
                             "This removes only the reference, not package files.")
                )
            target = "global Pi settings" if scope == "global" else "this project's Pi settings"
            effect = (
                f"Enable adds the package to {target}.\n"
                "Disable removes that reference, not package files."
            )
        else:
            link = pi_extension_dir(row.slug, scope=scope, home=home, project=project)
            effect = (
                "Enable connects the library source to Pi.\n"
                "Disable removes the connection, not source files.\n"
                f"Pi path: {escape(str(link))}"
            )

        if pending:
            action = "Enable" if pending == "link" else "Disable"
            controls = f"[yellow]Pending: {action} ({scope}).[/]\n[b]Ctrl+S[/] → apply"
        elif scope == "project" and row.global_cell.global_loaded and not loaded:
            state = "linked" if row.origin == "store-owned" else "enabled"
            controls = (
                f"Already {state} globally. No project change needed.\n"
                "To use it only in this project, disable globally first."
            )
        else:
            action = "Disable" if loaded else "Enable"
            controls = f"[b]Space[/] → queue {action} ({scope})\n[b]Ctrl+S[/] → apply"
        return f"{controls}\n\n{effect}\nRunning Pi sessions are unchanged."

    def _toggle_at(self, coord: Coordinate) -> None:
        visible = self._visible_rows()
        if coord.row >= len(visible):
            return
        row = visible[coord.row]

        # Untracked rows are non-interactive — no lock entry to act on.
        if row.origin in ("untracked", "local-package"):
            return

        if row.origin == "npm" and not row.managed:
            try:
                self.app.notify(
                    "npm reference not registered by Toolkit: see Info for removal",
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


        table.refresh()

    def _rebuild(self, table: DataTable) -> None:
        saved = table.cursor_coordinate
        # Preserve the viewport across clear() (#321): clear() resets scroll to
        # the top, so a toggle would jump the pane. Restore the offset below.
        # On the toggle path (cursor unchanged) the restored cursor stays in the
        # restored viewport, so Textual's deferred _scroll_cursor_into_view is a
        # no-op and the offset holds. See skill_grid._rebuild for the full note.
        saved_scroll = (table.scroll_x, table.scroll_y)
        extension_width = self._column_width(
            table, _COL_EXTENSION, self._text_width_for_extension_column()
        )
        source_width = current_source_column_width(table)
        table.clear(columns=True)
        # The asset column is explained by `i`, not header click (#479).
        table.add_column(asset_type_label("pi-extension"), width=extension_width)
        table.add_column(f"Pi {_INFO_GLYPH}", width=_SCOPE_COLUMN_WIDTH)
        table.add_column(f"Origin {_INFO_GLYPH}", width=_ORIGIN_COLUMN_WIDTH)
        table.add_column("Source", width=source_width)
        self._adjust_source_column_width(table)

        visible = self._visible_rows()
        for row in visible:
            cells: list[str | Text] = [
                Text(row.slug, no_wrap=True, overflow="ellipsis"),
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

    def _adjust_source_column_width(self, table: DataTable) -> None:
        if self.size.width > 0:
            set_source_column_width(table, self.size.width, _FIXED_COLUMN_WIDTH)

    def _text_width_for_extension_column(self) -> int:
        header_width = len(asset_type_label("pi-extension"))
        row_width = max((len(row.slug) for row in self._visible_rows()), default=0)
        return max(_DEFAULT_EXTENSION_WIDTH, header_width, row_width)

    @staticmethod
    def _column_width(table: DataTable, index: int, default: int) -> int:
        if len(table.columns) <= index:
            return default
        column_key = list(table.columns.keys())[index]
        return table.columns[column_key].width or default

    def _cell_glyph(self, *, row: PiExtensionRow, scope: str) -> str:
        """Return the display glyph for a scope cell. Never named _render_*."""
        if row.origin in ("untracked", "local-package"):
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
        return pi_extension_origin_label(row.origin)

    def _origin_glyph(self, row: PiExtensionRow) -> str:
        """Return styled markup for an origin label. Never named _render_*."""
        if row.origin == "npm":
            return "[cyan]npm[/]"
        return _ORIGIN_MARKUP.get(row.origin, pi_extension_origin_label(row.origin))
