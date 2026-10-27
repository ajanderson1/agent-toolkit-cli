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

Loose local rows configure native Pi selectors without taking file ownership.
Filesystem packages remain read-only; native npm controls need no registration.
"""
from __future__ import annotations

from pathlib import Path
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

Op = Literal["link", "unlink", "reset"]

_LOADED_GLYPH    = "[green]✔[/]"
_UNLOADED_GLYPH  = "☐"
_PENDING_LINK    = "[yellow]+[/]"
_PENDING_UNLINK  = "[yellow]-[/]"
_UNTRACKED_GLYPH = "[dim]—[/]"
_MIXED_GLYPH = "[yellow]◐[/]"
_INFO_GLYPH      = "ⓘ"
_GLOBAL_GLYPH    = "🌐"

_ORIGIN_MARKUP = {
    "store-owned": "[blue]library[/]",
    "catalog": "[cyan]catalog[/]",
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


from agent_toolkit_tui.widgets.catalog_pending import CatalogPendingMixin


class PiGrid(CatalogPendingMixin, Vertical):
    """One row per Pi extension; interactive cells for global + project scopes."""

    catalog_kind = "pi-extension"

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
        Binding("r", "reset_npm_selection", "Reset npm filter"),
    ]

    def __init__(self, rows: list[PiExtensionRow], *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._rows: list[PiExtensionRow] = sorted(rows, key=lambda r: r.slug)
        self._scope: Literal["global", "project"] = "global"
        # (scope: "global"|"project", slug) -> Op
        self._pending: dict[tuple[str, str], Op] = {}
        self._local_targets: dict[tuple[str, str], tuple[Path, ...]] = {}
        self._npm_snapshots: dict[tuple[str, str], str] = {}
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
        self._local_targets.clear()
        self._npm_snapshots.clear()
        try:
            table = self.query_one("#pi-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def set_scope(self, scope: Literal["global", "project"]) -> None:
        self._scope = scope
        self._pending.clear()
        self._local_targets.clear()
        self._npm_snapshots.clear()
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

    def pending_local_targets(self) -> dict[tuple[str, str], tuple[Path, ...]]:
        return dict(self._local_targets)

    def pending_npm_snapshots(self) -> dict[tuple[str, str], str]:
        return dict(self._npm_snapshots)

    def clear_pending(self) -> None:
        self._catalog_pending = {}
        self._pending.clear()
        self._local_targets.clear()
        self._npm_snapshots.clear()
        try:
            table = self.query_one("#pi-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def restore_pending(
        self, pending: dict[tuple[str, str], Op], *,
        local_targets: dict[tuple[str, str], tuple[Path, ...]] | None = None,
        npm_snapshots: dict[tuple[str, str], str] | None = None,
    ) -> None:
        self._pending.update(pending)
        self._capture_catalog_pending()
        if local_targets is not None:
            self._local_targets.update({key: paths for key, paths in local_targets.items() if key in pending})
        if npm_snapshots is not None:
            self._npm_snapshots.update({key: value for key, value in npm_snapshots.items() if key in pending})
        try:
            table = self.query_one("#pi-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def _project_install_blocked(self, *, row: PiExtensionRow, loaded: bool) -> bool:
        return row.origin not in ("untracked", "npm") and self._scope == "project" and row.global_cell.global_loaded and not loaded

    def _notify_pending(self) -> None:
        self._capture_catalog_pending()
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
        from agent_toolkit_tui.screens.cell_info import asset_info_body

        state_label = "Linked" if row.origin == "store-owned" else "Enabled"
        selection = self._selection_label(row, self._scope)
        glance_state = (
            selection if row.catalog_only or row.origin in ("npm", "local-package")
            else f"{state_label}: {selection}"
        )
        origin = {
            "store-owned": "library",
            "npm": "npm",
            "untracked": "local",
            "local-package": "local",
            "catalog": "catalog",
        }[row.origin]
        source = row.npm_state.for_scope(self._scope).source if row.npm_state else row.source
        self.app.push_screen(
            CellInfoScreen(
                title=f"{row.slug} · {asset_type_label('pi-extension')}",
                body_markup=asset_info_body(
                    asset_label=asset_type_label("pi-extension"),
                    slug=row.slug,
                    description=None,
                    description_location="Pi extension metadata",
                    source=source,
                    origin=origin,
                    ref=None,
                    state=glance_state,
                    scope=self._scope,
                    show_ref=False,
                    extra_lines=[
                        f"{state_label} globally: {self._selection_label(row, 'global')}",
                        f"{state_label} for this project: {self._selection_label(row, 'project')}",
                        self._info_body(row=row, scope=self._scope),
                    ],
                ),
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
        catalog = "\n".join(self._catalog_info(row))
        if row.catalog_only:
            return catalog
        return "\n\n".join(section for section in (
            self._extension_info_body(row), self._scope_info_body(row=row, scope=scope), catalog,
        ) if section)

    def _npm_info_body(self, row: PiExtensionRow, scope: str) -> str:
        from shlex import join
        if row.npm_state is None:
            return "Native npm state unavailable; refresh before changing selection."
        state = row.npm_state
        current = state.for_scope(scope)
        mode = {"inherit": "Inherited global policy", "override": "Project override of global package",
            "owned": "Scope-owned declaration", "available": "Available, not configured"}[current.mode]
        details = [f"Native Pi selection: {current.status}", mode,
            f"Installed version: {current.version or 'not installed'}",
            f"Installation: {current.root or 'missing in this scope'}"]
        if current.record is not None:
            declaration = current.record if isinstance(current.record, str) else current.record["source"]
            details.append(f"Scoped declaration: {declaration}")
        if current.scope_root is not None and current.scope_root != current.root:
            details.append(f"Separate scope installation (not selected): {current.scope_root} · {current.scope_version}")
        pending = self._pending.get((scope, row.slug))
        if pending:
            action = {"link": "Enable all extensions", "unlink": "Disable all extensions", "reset": "Reset extension policy"}[pending]
            details.append(f"Pending: {action} ({scope}). Ctrl+S → apply")
        elif current.ambiguous:
            details.append("Resolve multiple declarations for this npm identity in Pi settings before changing selection.")
        elif current.compatible and current.resources:
            action = "Disable" if current.enabled else "Enable"
            details.append(f"Space → queue {action} all extensions; Ctrl+S → apply")
        else:
            details.append("Install/repair this scope first; toggles never download packages.")
        details.extend([
            f"Selection affects this package's {len(current.resources)} extension entrypoints.",
            "Enable/Disable changes native package filters only; files and declarations are retained.",
            "Bundled skills, prompts and themes are unchanged by this checkbox.",
            "R → queue reset of this scope's extension filter; Ctrl+S → apply." if not current.ambiguous else "Selection/reset controls are unavailable for ambiguous declarations.",
        ])
        if scope == "project" and current.mode in ("inherit", "override"):
            details.append("Reset restores global inheritance; no separate project installation is needed.")
            details.append("To stop using this global package here, Disable here—not global uninstall.")
        elif not current.configured and not current.installed:
            details.append("No installation or declaration to remove in this scope.")
        else:
            command = ["agent-toolkit-cli", "pi-extensions", "remove", "npm:" + state.identity,
                "--global" if scope == "global" else "--project"]
            if current.external:
                command.append("--external")
                details.append("Externally installed npm package; removal needs explicit shared-installation confirmation.")
            details.append("Remove installation/declaration: " + join(command))
            details.append("Package removal also affects bundled resources. Other scopes and global fallback may remain active.")
        if scope == "project":
            details.append("Project resources still require Pi project trust; Toolkit does not grant it.")
        details.append("No Toolkit npm registration or second unregister step. Running Pi sessions are unchanged.")
        return escape("\n".join(details))

    def _scope_info_body(self, *, row: PiExtensionRow, scope: str) -> str:
        from pathlib import Path
        from agent_toolkit_cli.pi_extension_paths import (
            pi_extension_dir,
        )

        if row.origin == "untracked":
            pending = self._pending.get((scope, row.slug))
            loaded = row.global_cell.global_loaded if scope == "global" else row.project_cell.project_loaded
            action = ("Enable" if pending == "link" else "Disable") if pending else ("Disable" if loaded else "Enable")
            controls = (
                f"[yellow]Pending: {action} ({scope}).[/]\n[b]Ctrl+S[/] → apply"
                if pending else f"[b]Space[/] → queue {action} ({scope})\n[b]Ctrl+S[/] → apply"
            )
            paths = row.local_state.paths_for(scope) if row.local_state else ()
            package_paths = (row.local_state.global_package_paths if scope == "global" else row.local_state.project_package_paths) if row.local_state else ()
            if package_paths:
                guidance = "Selected through packages[]; edit that package reference. Loose selectors cannot override it."
                controls = controls + "\n" + guidance if pending else guidance
            if len(paths) > 1:
                controls += f"\n{action} affects all {len(paths)} entrypoints."
            details = [controls]
            if len(paths) > 1:
                details.append("Entrypoints:\n" + "\n".join(escape(str(path)) for path in paths))
            found = False
            for location in (scope, "global" if scope == "project" else "project"):
                base = pi_extension_dir(
                    row.slug, scope=location, home=Path.home(),
                    project=Path.cwd() if location == "project" else None,
                )
                for path in (base, base.with_name(base.name + ".ts"), base.with_name(base.name + ".js")):
                    if path.exists() or path.is_symlink():
                        found = True
                        details.append("\n".join([f"Location ({location}):", *local_path_info(path, configurable=True)]))
            if not found:
                details.extend("\n".join(local_path_info(path, configurable=True)) for path in paths)
            details.append("Running Pi sessions are unchanged.")
            return "\n\n".join(details)

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
            return (
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
            return self._npm_info_body(row, scope)
        link = pi_extension_dir(row.slug, scope=scope, home=home, project=project)
        effect = (
            "Enable connects the library source to Pi.\n"
            "Disable removes the connection, not source files.\n"
            f"Pi path: {link}"
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

        # Catalogue npm rows never enter the native selection or acquisition queue.
        if row.catalog_only and row.catalog_item.source_type == "npm":
            return
        # Filesystem packages retain their separate package/filter semantics.
        if row.origin == "local-package":
            return

        if row.origin == "npm" and row.npm_state is None:
            try:
                self.app.notify(
                    "Native npm state unavailable: refresh before changing selection",
                    severity="warning",
                )
            except Exception:
                pass
            return

        if coord.column != _COL_SCOPE:
            return
        scope = self._scope
        if row.npm_state and row.npm_state.for_scope(scope).ambiguous and (scope, row.slug) not in self._pending:
            self.app.notify("Multiple native npm declarations; resolve them in Pi settings first", severity="warning")
            return
        package_paths = (row.local_state.global_package_paths if scope == "global" else row.local_state.project_package_paths) if row.local_state else ()
        if package_paths and (scope, row.slug) not in self._pending:
            self.app.notify("Selected through packages[]; see Info for package configuration", severity="warning")
            return

        key = (scope, row.slug)
        if key in self._pending:
            del self._pending[key]
            self._local_targets.pop(key, None)
            self._npm_snapshots.pop(key, None)
        else:
            loaded = (
                row.global_cell.global_loaded
                if scope == "global"
                else row.project_cell.project_loaded
            )
            if self._project_install_blocked(row=row, loaded=loaded):
                return
            self._pending[key] = "unlink" if loaded else "link"
            if row.origin == "untracked":
                self._local_targets[key] = row.local_state.paths_for(scope) if row.local_state else ()
            elif row.npm_state is not None:
                self._npm_snapshots[key] = row.npm_state.snapshot_for(scope)

        try:
            table = self.query_one("#pi-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass
        self._notify_pending()


        table.refresh()

    def action_reset_npm_selection(self) -> None:
        table = self.query_one("#pi-table", DataTable)
        visible = self._visible_rows()
        if table.cursor_coordinate.row >= len(visible):
            return
        row = visible[table.cursor_coordinate.row]
        if row.npm_state is None:
            return
        key = (self._scope, row.slug)
        if row.npm_state.for_scope(self._scope).ambiguous and self._pending.get(key) != "reset":
            self.app.notify("Multiple native npm declarations; resolve them in Pi settings first", severity="warning")
            return
        if self._pending.get(key) == "reset":
            self._pending.pop(key)
            self._npm_snapshots.pop(key, None)
        else:
            self._pending[key] = "reset"
            self._npm_snapshots.setdefault(key, row.npm_state.snapshot_for(self._scope))
        self._rebuild(table)
        self._notify_pending()

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
                Text(row.npm_state.for_scope(self._scope).source if row.npm_state else row.source, no_wrap=True, overflow="ellipsis"),
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

    @staticmethod
    def _selection_label(row: PiExtensionRow, scope: str) -> str:
        if row.catalog_only:
            return "Not installed" if row.catalog_item.source_type == "npm" else "Not acquired"
        if row.npm_state:
            current = row.npm_state.for_scope(scope)
            return current.status + (" (inherited global)" if scope == "project" and current.mode == "inherit" else "")
        if row.local_state:
            package_paths = row.local_state.global_package_paths if scope == "global" else row.local_state.project_package_paths
            if package_paths:
                return "Package-controlled"
            entries = row.local_state.global_entries if scope == "global" else row.local_state.project_entries
            if any(e.enabled for e in entries) and not all(e.enabled for e in entries):
                return f"Mixed ({sum(e.enabled for e in entries)}/{len(entries)})"
        loaded = row.global_cell.global_loaded if scope == "global" else row.project_cell.project_loaded
        return "Yes" if loaded else "No"

    def _cell_glyph(self, *, row: PiExtensionRow, scope: str) -> str:
        """Return the display glyph for a scope cell. Never named _render_*."""
        if row.origin == "local-package" or (row.catalog_only and row.catalog_item.source_type == "npm"):
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
        elif pending == "reset":
            base = "[yellow]↺[/]"
        elif row.npm_state and (row.npm_state.for_scope(scope).missing or row.npm_state.for_scope(scope).ambiguous):
            base = "[yellow]![/]"
        elif row.npm_state and row.npm_state.for_scope(scope).mixed:
            base = _MIXED_GLYPH
        elif row.local_state and (row.local_state.global_package_paths if scope == "global" else row.local_state.project_package_paths):
            base = _UNTRACKED_GLYPH
        elif row.local_state and (row.local_state.global_mixed if scope == "global" else row.local_state.project_mixed):
            base = _MIXED_GLYPH
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
