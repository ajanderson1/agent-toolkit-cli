"""Interactive DataTable for the TUI's MCP tab (#398).

Columns are scope-dependent (parity-ported from agent_grid.py, #361/#374):

- Project: MCP | Standard (2) ⓘ | Codex ⓘ | OpenCode ⓘ | State ⓘ | Source.
- Global:  MCP | Claude ⓘ | Codex ⓘ | OpenCode ⓘ | Pi ⓘ | State ⓘ | Source.

Layout: [0]=slug, [1..N]=harnesses, [N+1]=state, [N+2]=source.

Mirrors agent_grid.py: per-harness columns, scope toggle, toggle-queue →
pending → apply. Pending key shape: (scope, harness_name, slug) — same
3-tuple as agent. The Standard column IS a harness column (the project
.mcp.json projection, #399, is a real installable destination) — it toggles
like any other. Clicking a glyphed header explains the column; `i` always
explains the selected MCP.

Two MCP-specific differences from agent_grid.py:
- The column set is derived PER SCOPE via mcp_interactive_harnesses(scope),
  NOT a frozen module constant — the Standard column exists only at project
  scope (mcp_standard_covered('global') raises KeyError). So set_scope MUST
  rebuild columns (the agent grid does NOT, because its set is scope-invariant).
- No 🌐 global marker — MCP never probes a (harness, "global") cell from a
  project view, and the design drops the marker (spec §10).

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

from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.display_names import (
    asset_type_label,
    harness_label,
    standard_column_header,
)
from agent_toolkit_tui.mcp_state import McpRow, mcp_interactive_harnesses
from agent_toolkit_tui.widgets._support import adjust_source_column_width
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal
from agent_toolkit_tui.widgets.filter_input import GridFilterInput

_LINKED_GLYPH   = "[green]✔[/]"
_UNLINKED_GLYPH = "☐"
_PENDING_LINK   = "[yellow]+[/]"
_PENDING_UNLINK = "[yellow]-[/]"
_INFO_GLYPH     = "ⓘ"

# Row-state badges (#360). `installed` renders as an em-dash to keep the
# common case quiet; `library` mirrors skill_grid's dim available state;
# `unlisted` gets a warning tint.
_STATE_MARKUP = {
    "installed": "[dim]—[/]",
    "library": "[dim]library[/]",
    "unlisted": "[yellow]unlisted[/]",
}

Op = Literal["link", "unlink"]


class McpGrid(Vertical):
    """One row per MCP slug; interactive cells for the per-scope harness set."""

    class PendingChanged(Message):
        """Posted whenever the pending toggle set changes.

        Carries the current pending count so the App can refresh the footer
        "Pending: N" label live as the user toggles cells.
        """

        def __init__(self, count: int) -> None:
            super().__init__()
            self.count = count

    DEFAULT_CSS = """
    McpGrid { border: round $primary; }
    McpGrid DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("space", "toggle_cell", "Toggle", priority=True),
        Binding("a", "toggle_column", "All/None", priority=True),
        Binding("i", "info", "Info", priority=True),
    ]

    def __init__(self, rows: list[McpRow], *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._rows = sorted(rows, key=lambda r: r.slug)
        self._scope: Literal["global", "project"] = "global"
        self._last_resize: Resize | None = None
        # (scope, harness_name, slug) -> op
        self._pending: dict[tuple[str, str, str], Op] = {}
        self._filter: str = ""

    def _harnesses(self) -> tuple[str, ...]:
        """Rendered harness columns for the active scope (NOT a constant —
        the set differs by scope; standard appears only at project)."""
        return mcp_interactive_harnesses(self._scope)

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def row_slugs(self) -> list[str]:
        return [r.slug for r in self._rows]

    def set_rows(self, rows: list[McpRow]) -> None:
        self._rows = sorted(rows, key=lambda r: r.slug)
        self._pending.clear()
        try:
            table = self.query_one("#mcp-table", DataTable)
        except Exception:
            return
        self._rebuild(table)

    def set_scope(self, scope: Literal["global", "project"]) -> None:
        self._scope = scope
        self._pending.clear()
        # MCP's column set is scope-dependent — rebuild now (the agent grid
        # skips this because its columns are scope-invariant). Guard for the
        # pre-mount case where the DataTable isn't queryable yet.
        try:
            self._rebuild(self.query_one("#mcp-table", DataTable))
        except Exception:
            pass  # not mounted yet; set_rows will rebuild on first render

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
            table = self.query_one("#mcp-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def restore_pending(self, pending: dict[tuple[str, str, str], Op]) -> None:
        self._pending.update(pending)
        try:
            table = self.query_one("#mcp-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        yield GridFilterInput(table_selector="#mcp-table", id="mcp-filter")
        table: DataTable[str] = DataTable(
            id="mcp-table", cursor_type="cell", zebra_stripes=True,
        )
        yield table

    def set_filter(self, text: str) -> None:
        self._filter = text.strip().lower()
        try:
            table = self.query_one("#mcp-table", DataTable)
        except Exception:
            return
        self._rebuild(table)

    def _visible_rows(self) -> list[McpRow]:
        if self._filter:
            return [row for row in self._rows if self._filter in row.slug.lower()]
        return list(self._rows)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "mcp-filter":
            self.set_filter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "mcp-filter":
            try:
                self.query_one("#mcp-table", DataTable).focus()
            except Exception:
                pass

    def on_mount(self) -> None:
        try:
            table = self.query_one("#mcp-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def on_resize(self, event: Resize) -> None:
        self._last_resize = event
        try:
            table = self.query_one("#mcp-table", DataTable)
        except Exception:
            return
        self._adjust_source_width(table, event)

    def action_toggle_cell(self) -> None:
        try:
            table = self.query_one("#mcp-table", DataTable)
        except Exception:
            return
        self._toggle_at(table.cursor_coordinate)

    def action_info(self) -> None:
        """Open the selected MCP's asset panel, regardless of column (#479)."""
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen, asset_info_body

        try:
            table = self.query_one("#mcp-table", DataTable)
        except Exception:
            return
        visible = self._visible_rows()
        if table.cursor_coordinate.row >= len(visible):
            return
        row = visible[table.cursor_coordinate.row]
        self.app.push_screen(
            CellInfoScreen(
                title=f"{row.slug} · {asset_type_label('mcp')}",
                body_markup=asset_info_body(
                    asset_label=asset_type_label("mcp"),
                    slug=row.slug,
                    description=None,
                    description_location="MCP definition",
                    source=row.source,
                    ref=row.pin,
                    state=row.state,
                    scope=self._scope,
                ),
            )
        )

    def action_toggle_column(self) -> None:
        """Toggle all rows in the column under the cursor."""
        try:
            table = self.query_one("#mcp-table", DataTable)
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
            table = self.query_one("#mcp-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass
        self._notify_pending()

    def _column_index(self, harness_name: str) -> int:
        """Return the table column index for a harness name. Layout: [0]=slug, [1..N]=harnesses, [N+1]=state, [N+2]=source."""
        try:
            return 1 + list(self._harnesses()).index(harness_name)
        except ValueError:
            return -1

    def _harness_for_column(self, col: int) -> str | None:
        """Return the harness name for a table column index, or None for slug/state/source cols. Layout: [0]=slug, [1..N]=harnesses, [N+1]=state, [N+2]=source."""
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
                    asset_type="mcp",
                    context=self._context_for(
                        key=key,
                        row_index=event.data_table.cursor_coordinate.row,
                    ),
                )
            )
        )

    def _context_for(self, *, key: str, row_index: int) -> dict[str, object]:
        """Return scope from the live grid; MCP has no cross-scope marker."""
        del key, row_index
        return {"scope": self._scope}

    def on_resize(self, event: Resize) -> None:
        try:
            table = self.query_one("#mcp-table", DataTable)
        except Exception:
            return

        adjust_source_column_width(table, event, self._fixed_column_width())

    def _fixed_column_width(self) -> int:
        """Width used by every column before Source."""
        return 22 + (16 * len(self._harnesses())) + 10

    def _adjust_source_width(self, table: DataTable, event: Resize) -> None:
        adjust_source_column_width(
            table, event, fixed_width=self._fixed_column_width()
        )

    def _rebuild(self, table: DataTable) -> None:
        """Rebuild the DataTable from current rows + pending. Never named _render_*."""
        saved = table.cursor_coordinate
        # Preserve the viewport across clear() (#321): clear() resets scroll to
        # the top, so a toggle would jump the pane. Restore the offset below.
        saved_scroll = (table.scroll_x, table.scroll_y)
        source_width = current_source_column_width(table)
        table.clear(columns=True)
        # The asset column is explained by `i`, not header click (#479).
        table.add_column(asset_type_label("mcp"), width=22)
        # Per-harness columns, derived per scope. "standard" is the project
        # .mcp.json projection (#399, #398), not a catalog harness — label it
        # with the covered count so the fold is legible without pressing `i`
        # (review F9): "Standard (2) ⓘ" tells the user this one cell stands for
        # 2 harnesses. project-only, so covered is always a set there.
        harnesses = self._harnesses()
        standard_header = standard_column_header("mcp", self._scope)
        if standard_header is None:
            assert "standard" not in harnesses, (
                "mcp header rule has no standard slot, but _harnesses() rendered one"
            )
            headers: dict[str, str] = {}
        else:
            assert "standard" in harnesses, (
                "mcp header rule has a standard slot, but _harnesses() omitted it"
            )
            headers = {"standard": standard_header}
        for harness in harnesses:
            base = headers.get(harness, harness_label(harness))
            table.add_column(f"{base} {_INFO_GLYPH}", width=16)
        # State column — explains its asset-type-specific badges (#479).
        table.add_column(f"State {_INFO_GLYPH}", width=10)
        # Source column — passive, no info popup.
        table.add_column("Source", width=source_width)

        visible = self._visible_rows()
        for row in visible:
            cells: list[str | Text] = [row.slug]
            for harness in self._harnesses():
                cells.append(self._cell_glyph(row=row, harness=harness))
            cells.append(_STATE_MARKUP.get(row.state, row.state))
            cells.append(Text(row.source, no_wrap=True, overflow="ellipsis"))
            table.add_row(*cells, key=f"mcp:{row.slug}")

        if visible:
            max_row = len(visible) - 1
            # Layout: slug + N harness cols + state + source.
            max_col = 2 + len(self._harnesses())
            table.cursor_coordinate = Coordinate(
                row=min(saved.row, max_row),
                column=min(saved.column, max_col),
            )
        if self._last_resize is not None:
            self._adjust_source_width(table, self._last_resize)
        # Pin the viewport back (clamped by Textual to the new content range).
        table.scroll_to(
            x=saved_scroll[0], y=saved_scroll[1], animate=False, force=True
        )

    def _cell_glyph(self, *, row: McpRow, harness: str) -> str:
        """Return the display glyph for a harness cell. Never named _render_*."""
        cell = row.cells.get((harness, self._scope))
        if cell is None:
            # Not applicable at this scope (e.g. standard at global).
            return "[dim]—[/]"
        pending = self._pending.get((self._scope, harness, row.slug))
        if pending == "link":
            return _PENDING_LINK
        if pending == "unlink":
            return _PENDING_UNLINK
        return _LINKED_GLYPH if cell.linked else _UNLINKED_GLYPH
