"""Interactive DataTable for the TUI's instruction tab.

Columns (#351): INSTRUCTION ⓘ | standard ⓘ | <non-covered main harnesses…> | Source.

Mirrors agent_grid.py: per-harness columns, scope toggle, toggle-queue →
pending → apply. Pending key shape: (scope, harness_name, slug) — same
3-tuple as skill/agent.

The `standard` column is read-only (canonical_exists status). It is NOT
toggleable. Conflict cells are also not toggleable (adapter refuses; shown
distinctly as [red]![/]).

CRITICAL: never name any method `_render_*` — it collides with Textual's
internal flag mechanism and produces "bool is not callable" from compose.
All glyph helpers are named `_cell_glyph`, `_standard_glyph`, `_rebuild`.
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

from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.composition import instructions_nonstandard_main
from agent_toolkit_tui.display_names import asset_type_label, harness_label, standard_label
from agent_toolkit_tui.instruction_state import InstructionRow
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal
from agent_toolkit_tui.widgets.filter_input import GridFilterInput

_LINKED_GLYPH    = "[green]✔[/]"
_UNLINKED_GLYPH  = "☐"
_CONFLICT_GLYPH  = "[red]![/]"
_PENDING_LINK    = "[yellow]+[/]"
_PENDING_UNLINK  = "[yellow]-[/]"
_INFO_GLYPH      = "ⓘ"
_NOT_AVAIL_GLYPH = "[dim]—[/]"
_GLOBAL_GLYPH    = "🌐"

# Column index offsets:
#   0 = slug (INSTRUCTION)
#   1 = standard (read-only canonical status)
#   2..2+N-1 = active harness columns (_active_harnesses())
#   2+N = Source
_HARNESS_COL_OFFSET = 2

Op = Literal["link", "unlink"]


def _standard_count() -> int:
    from agent_toolkit_cli.instructions_matrix import instructions_matrix_rows

    return sum(1 for row in instructions_matrix_rows() if row["verdict"] == "native")


class InstructionGrid(Vertical):
    """One row per locked slug; interactive cells for the active harness columns."""

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
        Binding("a", "toggle_column", "All/None", priority=True),
        Binding("i", "info", "Info", priority=True),
    ]

    def __init__(self, rows: list[InstructionRow], *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._rows = sorted(rows, key=lambda r: r.slug)
        self._scope: Literal["global", "project"] = "global"
        # (scope, harness_name, slug) -> op
        self._pending: dict[tuple[str, str, str], Op] = {}
        self._filter: str = ""

    def _active_harnesses(self) -> tuple[str, ...]:
        # Standard column + non-covered main harnesses. The long tail is
        # CLI-only (#351 post-demo decision).
        return instructions_nonstandard_main()

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def row_slugs(self) -> list[str]:
        return [r.slug for r in self._rows]

    def set_rows(self, rows: list[InstructionRow]) -> None:
        self._rows = sorted(rows, key=lambda r: r.slug)
        self._pending.clear()
        try:
            table = self.query_one("#instruction-table", DataTable)
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

    def compose(self) -> ComposeResult:
        yield GridFilterInput(table_selector="#instruction-table", id="instruction-filter")
        table: DataTable[str] = DataTable(
            id="instruction-table", cursor_type="cell", zebra_stripes=True,
        )
        yield table

    def set_filter(self, text: str) -> None:
        self._filter = text.strip().lower()
        try:
            table = self.query_one("#instruction-table", DataTable)
        except Exception:
            return
        self._rebuild(table)

    def _visible_rows(self) -> list[InstructionRow]:
        if self._filter:
            return [row for row in self._rows if self._filter in row.slug.lower()]
        return list(self._rows)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "instruction-filter":
            self.set_filter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "instruction-filter":
            try:
                self.query_one("#instruction-table", DataTable).focus()
            except Exception:
                pass

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
        """Route `i` by column. The standard column has registered ColumnInfo
        and opens ColumnInfoModal — the registry path that replaced the old
        inline column-1 branch (#351). Everything else opens CellInfoScreen
        with the per-cell state."""
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen

        try:
            table = self.query_one("#instruction-table", DataTable)
        except Exception:
            return
        coord = table.cursor_coordinate
        key = self._column_key_for_index(coord.column)
        if key is not None:
            info = get_column_info(
                key, context=self._context_for(key=key, row_index=coord.row)
            )
            if info is not None:
                self.app.push_screen(ColumnInfoModal(info))
                return
        visible = self._visible_rows()
        if coord.row >= len(visible):
            return
        row = visible[coord.row]

        if coord.column == 0:
            # Slug column — show instruction summary.
            if self._scope == "global":
                from agent_toolkit_cli.instructions_paths import global_canonical_agents_md
                canonical_path = global_canonical_agents_md()
            else:
                # Project scope: the app uses cwd as the project root (see
                # TUIApp._scope_to_roots), so resolve the canonical relative to
                # it. Passing None here would crash (project_canonical_agents_md
                # requires a real Path).
                from pathlib import Path

                from agent_toolkit_cli.instructions_paths import project_canonical_agents_md
                canonical_path = project_canonical_agents_md(Path.cwd())
            title = f"{row.slug} · instruction"
            body = (
                f"Instruction [b]{row.slug}[/]\n"
                f"Source: {row.source}\n"
                f"Scope:  {self._scope}\n"
                f"Canonical: {canonical_path}"
            )
        else:
            harness = self._harness_for_column(coord.column)
            if harness is None:
                return
            cell = row.cells.get((harness, self._scope))
            scope_flag = "-g" if self._scope == "global" else "-p"
            display = harness_label(harness)
            title = f"{row.slug} · {display} @ {self._scope}"
            pending = self._pending.get((self._scope, harness, row.slug))
            if pending == "link":
                body = (
                    "[yellow]Pending: install pointer.[/]\n\n"
                    "Press [b]^s[/] to apply."
                )
            elif pending == "unlink":
                body = (
                    "[yellow]Pending: remove pointer.[/]\n\n"
                    "Press [b]^s[/] to apply."
                )
            elif cell is None:
                body = f"Not available at {self._scope} scope."
            elif cell.conflict:
                body = (
                    f"[red]Conflict![/] The pointer slot for {display} is occupied "
                    "by a real file or foreign symlink.\n\n"
                    "Resolve manually before installing:\n"
                    "  Move or delete the conflicting file, then re-run install.\n\n"
                    f"CLI: [b]agent-toolkit-cli instructions install {scope_flag}[/]"
                )
            elif cell.linked:
                body = (
                    f"Installed. Pointer for {display} @ {self._scope} is active.\n\n"
                    f"CLI: [b]agent-toolkit-cli instructions uninstall {scope_flag}[/]"
                )
            else:
                body = (
                    f"Not installed. Press [b]space[/] to queue install "
                    f"into {display} @ {self._scope}.\n\n"
                    f"Or from the CLI:\n"
                    f"  [b]agent-toolkit-cli instructions install {scope_flag}[/]"
                )

        self.app.push_screen(CellInfoScreen(title=title, body_markup=body))

    def action_toggle_column(self) -> None:
        """Toggle all rows in the column under the cursor."""
        try:
            table = self.query_one("#instruction-table", DataTable)
        except Exception:
            return
        col = table.cursor_coordinate.column
        harness = self._harness_for_column(col)
        if harness is None:
            # slug or standard or source — no-op.
            return
        scope = self._scope
        # Determine target: if any cell in the column is effectively off → link all.
        any_off = False
        for r in self._rows:
            cell = r.cells.get((harness, scope))
            if cell is None or cell.conflict:
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
            if cell is None or cell.conflict:
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
        # Slug column (0), standard column (1), or source column → no-op.
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
        if cell.conflict:
            # Conflict cell — adapter would refuse; do not queue.
            return
        key = (self._scope, harness, row.slug)
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
        """Return the harness name for a table column index, or None.

        Column layout:
          0 = slug (INSTRUCTION)
          1 = standard (read-only)
          2..2+N-1 = _active_harnesses()
          2+N = Source
        """
        if col < _HARNESS_COL_OFFSET:
            # Slug or standard — not an interactive harness column.
            return None
        active = self._active_harnesses()
        idx = col - _HARNESS_COL_OFFSET
        if 0 <= idx < len(active):
            return active[idx]
        return None

    def _column_key_for_index(self, col: int) -> str | None:
        """Resolve a column index to a COLUMN_INFO registry key (#351).

        Only the standard column has registered ColumnInfo; harness/slug/
        source columns return None and fall through to CellInfoScreen.
        """
        if col == 1:
            return "standard"
        return None

    def _context_for(self, *, key: str, row_index: int | None = None) -> dict | None:
        """Context for get_column_info(). The standard panel enumerates the
        native AGENTS.md readers from the harness-matrix SSOT (#351) and, when
        a row is focused, reports whether that row's slot is linked globally so
        the 🌐 marker block renders (#388, mirrors agent_grid._context_for)."""
        if key == "standard":
            from agent_toolkit_cli.instructions_matrix import instructions_matrix_rows

            native = tuple(
                r["harness"] for r in instructions_matrix_rows()
                if r["verdict"] == "native"
            )
            global_linked = False
            visible = self._visible_rows()
            if row_index is not None and 0 <= row_index < len(visible):
                row = visible[row_index]
                global_linked = any(
                    cell.linked
                    for (harness, scope), cell in row.cells.items()
                    if scope == "global"
                )
            return {
                "asset_type": "instructions",
                "names": native,
                "global_linked": global_linked,
            }
        return None

    def on_resize(self, event: Resize) -> None:
        try:
            table = self.query_one("#instruction-table", DataTable)
        except Exception:
            return

        fixed_width = 22 + 16 + (len(self._active_harnesses()) * 14)
        adjust_source_column_width(table, event, fixed_width)

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
        # Slug column.
        table.add_column(f"{asset_type_label('instruction')} {_INFO_GLYPH}", width=22)
        # Standard column — read-only canonical status. It leads; everything
        # after it is implicitly non-standard (group-tag header row removed
        # per AJ demo feedback, #351).
        table.add_column(f"{standard_label(_standard_count())} {_INFO_GLYPH}", width=16)
        # Per-harness interactive columns.
        active = self._active_harnesses()
        for harness in active:
            display = harness_label(harness)
            table.add_column(f"{display} {_INFO_GLYPH}", width=14)
        # Source column — passive.
        table.add_column("Source", width=source_width)

        visible = self._visible_rows()
        for row in visible:
            cells: list[str | Text] = [row.slug]
            cells.append(self._standard_glyph(row))
            for harness in active:
                cells.append(self._cell_glyph(row=row, harness=harness))
            cells.append(Text(row.source, no_wrap=True, overflow="ellipsis"))
            table.add_row(*cells, key=f"instruction:{row.slug}")

        if visible:
            max_row = len(visible) - 1
            # Layout: slug + standard + N harness cols + source.
            max_col = _HARNESS_COL_OFFSET + len(active)
            table.cursor_coordinate = Coordinate(
                row=min(saved.row, max_row),
                column=min(saved.column, max_col),
            )
        # Pin the viewport back (clamped by Textual to the new content range).
        table.scroll_to(
            x=saved_scroll[0], y=saved_scroll[1], animate=False, force=True
        )

    def _standard_glyph(self, row: InstructionRow) -> str:
        """Return display glyph for the standard/native AGENTS.md column."""
        if row.canonical_exists:
            return "[dim]AGENTS.md[/]"
        return "[red]missing[/]"

    def _cell_glyph(self, *, row: InstructionRow, harness: str) -> str:
        """Return the display glyph for a harness cell. Never named _render_*."""
        cell = row.cells.get((harness, self._scope))
        if cell is None:
            base = _NOT_AVAIL_GLYPH
        elif cell.conflict:
            base = _CONFLICT_GLYPH
        else:
            pending = self._pending.get((self._scope, harness, row.slug))
            if pending == "link":
                base = _PENDING_LINK
            elif pending == "unlink":
                base = _PENDING_UNLINK
            else:
                base = _LINKED_GLYPH if cell.linked else _UNLINKED_GLYPH
        # In project scope, mark cells whose harness slot is also linked
        # globally — same indicator as skills/agents/pi (#388). InstructionCell
        # has no drift/stray/skipped, so linked is the whole gate. Appends to
        # any base, including the not-applicable em-dash and the conflict glyph.
        if self._scope == "project":
            global_cell = row.cells.get((harness, "global"))
            if global_cell is not None and global_cell.linked:
                return f"{base} {_GLOBAL_GLYPH}"
        return base
