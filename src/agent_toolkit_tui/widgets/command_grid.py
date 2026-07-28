"""Interactive DataTable for the TUI's command tab.

Columns: Command | Standard (N) ⓘ | Pi ⓘ | Gemini ⓘ | State ⓘ | Source.

Commands have a live Standard slot (#482): one `.claude/commands/<slug>.md`
file covers Claude Code + Neovate (and project-scope Devin as a skill). Pi
and Gemini remain individual columns; Codex is CLI-only. Clicking a glyphed
header explains the column; `i` always explains the selected command.

Layout: [0]=slug, [1]=standard, [2..N]=nonstandard harnesses, [N+1]=state,
[N+2]=source.

Mirrors skill_grid.py: per-harness columns, scope toggle, toggle-queue →
pending → apply. Pending key shape: (scope, harness_name, slug) — same
3-tuple as skill.

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
from textual.events import Resize
from textual.message import Message
from textual.widgets import DataTable, Input
from textual.events import Resize
from rich.text import Text
from agent_toolkit_tui.widgets._support import adjust_source_column_width, current_source_column_width

from agent_toolkit_tui.command_state import CommandRow, interactive_harnesses
from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.display_names import asset_type_label, harness_label, standard_column_header
from agent_toolkit_tui.widgets._support import (
    adjust_source_column_width,
    set_source_column_width,
)
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal
from agent_toolkit_tui.widgets.filter_input import GridFilterInput

_LINKED_GLYPH   = "[green]✔[/]"
_UNLINKED_GLYPH = "☐"
_PENDING_LINK   = "[yellow]+[/]"
_PENDING_UNLINK = "[yellow]-[/]"
_INFO_GLYPH     = "ⓘ"
_GLOBAL_GLYPH   = "🌐"
_COMMAND_COL_WIDTH = 22
_HARNESS_COL_WIDTH = 14
_STATE_COL_WIDTH = 10
_SOURCE_COL_WIDTH = 30

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
    """One row per locked command with selection-aware harness cells."""

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
        self._selection: tuple[str, ...] | None = None
        self._filter: str = ""

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
        try:
            if self.is_mounted:
                self._rebuild(self.query_one("#command-table", DataTable))
        except Exception:
            pass

    def _harnesses(self) -> tuple[str, ...]:
        return interactive_harnesses(self._scope, self._selection)

    def set_harness_selection(self, selection: tuple[str, ...]) -> None:
        """Apply a presentation-only harness filter and rebuild columns."""
        self._selection = selection
        try:
            self._rebuild(self.query_one("#command-table", DataTable))
        except Exception:
            pass

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
        yield GridFilterInput(table_selector="#command-table", id="command-filter")
        table: DataTable[str] = DataTable(
            id="command-table", cursor_type="cell", zebra_stripes=True,
        )
        yield table

    def set_filter(self, text: str) -> None:
        self._filter = text.strip().lower()
        try:
            table = self.query_one("#command-table", DataTable)
        except Exception:
            return
        self._rebuild(table)

    def _visible_rows(self) -> list[CommandRow]:
        if self._filter:
            return [row for row in self._rows if self._filter in row.slug.lower()]
        return list(self._rows)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "command-filter":
            self.set_filter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "command-filter":
            try:
                self.query_one("#command-table", DataTable).focus()
            except Exception:
                pass

    def on_mount(self) -> None:
        try:
            table = self.query_one("#command-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def on_resize(self, event: Resize) -> None:
        try:
            table = self.query_one("#command-table", DataTable)
        except Exception:
            return
        adjust_source_column_width(
            table,
            event,
            fixed_width=self._fixed_column_width(),
        )

    def action_toggle_cell(self) -> None:
        try:
            table = self.query_one("#command-table", DataTable)
        except Exception:
            return
        self._toggle_at(table.cursor_coordinate)

    def action_info(self) -> None:
        """Open the selected command's asset panel, regardless of column (#479)."""
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen, asset_info_body

        try:
            table = self.query_one("#command-table", DataTable)
        except Exception:
            return
        visible = self._visible_rows()
        if table.cursor_coordinate.row >= len(visible):
            return
        row = visible[table.cursor_coordinate.row]
        self.app.push_screen(
            CellInfoScreen(
                title=f"{row.slug} · {asset_type_label('command')}",
                body_markup=asset_info_body(
                    asset_label=asset_type_label("command"),
                    slug=row.slug,
                    description=None,
                    description_location="command markdown",
                    source=row.source,
                    ref=row.ref,
                    state=row.state,
                    scope=self._scope,
                ),
            )
        )

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
        visible = self._visible_rows()
        if coord.row >= len(visible):
            return
        row = visible[coord.row]
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
        """Return the table column index for a harness name."""
        try:
            return 1 + self._harnesses().index(harness_name)
        except ValueError:
            return -1

    def _harness_for_column(self, col: int) -> str | None:
        """Return the harness for a table column, excluding metadata columns."""
        if col < 1:
            return None
        idx = col - 1
        harnesses = self._harnesses()
        if 0 <= idx < len(harnesses):
            return harnesses[idx]
        return None

    def _column_key_for_index(self, col: int) -> str | None:
        """Resolve every explainable header to its registry key (#479 R2)."""
        harness = self._harness_for_column(col)
        if harness is not None:
            return harness
        if col == len(self._harnesses()) + 1:
            return "state"
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
                    asset_type="command",
                    context=self._context_for(
                        key=key,
                        row_index=event.data_table.cursor_coordinate.row,
                    ),
                )
            )
        )

    def _context_for(self, *, key: str, row_index: int) -> dict[str, object]:
        """Return scope from the live grid for Standard/harness info panels."""
        del key, row_index
        return {"scope": self._scope}

    def on_resize(self, event: Resize) -> None:
        try:
            table = self.query_one("#command-table", DataTable)
        except Exception:
            return

        adjust_source_column_width(table, event, self._fixed_column_width())

    def _rebuild(self, table: DataTable) -> None:
        """Rebuild the DataTable from current rows + pending. Never named _render_*."""
        saved = table.cursor_coordinate
        # Preserve the viewport across clear() (#321): clear() resets scroll to
        # the top, so a toggle would jump the pane. Restore the offset below.
        # On the toggle path (cursor unchanged) the restored cursor stays in the
        # restored viewport, so Textual's deferred _scroll_cursor_into_view is a
        # no-op and the offset holds. See skill_grid._rebuild for the full note.
        saved_scroll = (table.scroll_x, table.scroll_y)
        source_width = current_source_column_width(table)
        table.clear(columns=True)
        # The asset column is explained by `i`, not header click (#479).
        table.add_column("Command", width=_COMMAND_COL_WIDTH)
        # Standard-first: Standard (N) then Pi/Gemini (#482).
        harnesses = self._harnesses()
        for harness in harnesses:
            if harness == "standard":
                header = standard_column_header("command", self._scope)
                assert header is not None, "commands always have a Standard slot"
                label = f"{header} {_INFO_GLYPH}"
            else:
                label = f"{harness_label(harness)} {_INFO_GLYPH}"
            table.add_column(label, width=_HARNESS_COL_WIDTH)
        # State column — explains its asset-type-specific badges (#479).
        table.add_column(f"State {_INFO_GLYPH}", width=_STATE_COL_WIDTH)
        # Source column — passive, no info popup.
        table.add_column("Source", width=source_width)
        self._adjust_source_column_width(table)

        visible = self._visible_rows()
        for row in visible:
            cells: list[str | Text] = [row.slug]
            for harness in harnesses:
                cells.append(self._cell_glyph(row=row, harness=harness))
            cells.append(_STATE_MARKUP.get(row.state, row.state))
            cells.append(Text(row.source, no_wrap=True, overflow="ellipsis"))
            table.add_row(*cells, key=f"command:{row.slug}")

        if visible:
            max_row = len(visible) - 1
            # Layout: slug + N harness cols + state + source.
            max_col = 2 + len(harnesses)
            table.cursor_coordinate = Coordinate(
                row=min(saved.row, max_row),
                column=min(saved.column, max_col),
            )
        # Pin the viewport back (clamped by Textual to the new content range).
        table.scroll_to(
            x=saved_scroll[0], y=saved_scroll[1], animate=False, force=True
        )

    def _fixed_column_width(self) -> int:
        return (
            _COMMAND_COL_WIDTH
            + (_HARNESS_COL_WIDTH * len(self._harnesses()))
            + _STATE_COL_WIDTH
        )

    def _adjust_source_column_width(self, table: DataTable) -> None:
        if self.size.width > 0:
            set_source_column_width(
                table, self.size.width, self._fixed_column_width()
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
