"""Interactive DataTable for the TUI's MCP tab (#398).

Columns are scope-dependent (parity-ported from agent_grid.py, #361/#374):

- Project: MCP ⓘ | Standard (2) ⓘ | codex ⓘ | opencode ⓘ | State | Source.
- Global:  MCP ⓘ | claude-code ⓘ | codex ⓘ | opencode ⓘ | pi ⓘ | State | Source.

Layout: [0]=slug, [1..N]=harnesses, [N+1]=state, [N+2]=source.

Mirrors agent_grid.py: per-harness columns, scope toggle, toggle-queue →
pending → apply. Pending key shape: (scope, harness_name, slug) — same
3-tuple as agent. The Standard column IS a harness column (the project
.mcp.json projection, #399, is a real installable destination) — it toggles
like any other; `i` on it opens the registry-backed ColumnInfoModal listing
the covered harnesses ({claude-code, pi}).

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
from textual.message import Message
from textual.widgets import DataTable, Input
from textual.events import Resize
from rich.text import Text
from agent_toolkit_tui.widgets._support import adjust_source_column_width, current_source_column_width

from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.display_names import asset_type_label, harness_label, standard_label
from agent_toolkit_tui.mcp_state import McpRow, mcp_interactive_harnesses
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

    def action_toggle_cell(self) -> None:
        try:
            table = self.query_one("#mcp-table", DataTable)
        except Exception:
            return
        self._toggle_at(table.cursor_coordinate)

    def action_info(self) -> None:
        """Route `i` by column. The standard column has registered ColumnInfo
        and opens ColumnInfoModal — the registry path mirroring
        agent_grid (#351/#361). Everything else opens CellInfoScreen
        with the per-cell state."""
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen

        try:
            table = self.query_one("#mcp-table", DataTable)
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
        visible = self._visible_rows()
        if coord.row >= len(visible):
            return
        row = visible[coord.row]

        if coord.column == 0:
            title = f"{row.slug} · mcp"
            body = (
                f"MCP [b]{row.slug}[/]\n"
                f"Source: {row.source}\n"
                f"Pin:    {row.pin or '—'}\n"
                f"State:  {'—' if row.state == 'installed' else row.state}"
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
                body = f"Installed.\nMCP {row.slug} is projected into {display} @ {self._scope}."
            else:
                body = (
                    f"Not installed.\nPress [b]space[/] to queue install "
                    f"into {display} @ {self._scope}.\n\n"
                    f"Or from the CLI:\n"
                    f"  [b]agent-toolkit-cli mcp install {row.slug} "
                    f"{scope_flag} --harness {harness}[/]"
                )

        self.app.push_screen(CellInfoScreen(title=title, body_markup=body))

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
        """Resolve a column index to a COLUMN_INFO registry key (#361).

        Only the standard column has registered ColumnInfo; harness/slug/
        source columns return None and fall through to CellInfoScreen.
        """
        if self._harness_for_column(col) == "standard":
            return "standard"
        return None

    def _context_for(self, *, key: str, row_index: int) -> dict | None:
        if key == "standard":
            from agent_toolkit_cli.mcp_standard import mcp_standard_covered
            covered = sorted(mcp_standard_covered("project"))
            return {
                "asset_type": "mcps",
                "names": tuple(covered),
                # Spell out the toggle consequence so the fold isn't a mystery
                # (review F9): one cell = N harnesses, project-scope only.
                "extra_lines": [
                    "",
                    f"Toggling this cell installs into all {len(covered)} at once "
                    "(one shared .mcp.json entry).",
                    "Project scope only — at global scope these are separate columns.",
                ],
                "global_linked": False,  # MCP standard is project-only; no 🌐 marker
            }
        return None

    def on_resize(self, event: Resize) -> None:
        try:
            table = self.query_one("#mcp-table", DataTable)
        except Exception:
            return

        fixed_width = 22 + 10 + (len(self._harnesses()) * 16)
        adjust_source_column_width(table, event, fixed_width)

    def _rebuild(self, table: DataTable) -> None:
        """Rebuild the DataTable from current rows + pending. Never named _render_*."""
        saved = table.cursor_coordinate
        # Preserve the viewport across clear() (#321): clear() resets scroll to
        # the top, so a toggle would jump the pane. Restore the offset below.
        saved_scroll = (table.scroll_x, table.scroll_y)
        source_width = current_source_column_width(table)
        table.clear(columns=True)
        # Slug column — info glyph since `i` works on it.
        table.add_column(f"{asset_type_label('mcp')} {_INFO_GLYPH}", width=22)
        # Per-harness columns, derived per scope. "standard" is the project
        # .mcp.json projection (#399, #398), not a catalog harness — label it
        # with the covered count so the fold is legible without pressing `i`
        # (review F9): "Standard (2) ⓘ" tells the user this one cell stands for
        # 2 harnesses. project-only, so covered is always a set there.
        for harness in self._harnesses():
            if harness == "standard":
                from agent_toolkit_cli.mcp_standard import mcp_standard_covered

                base = standard_label(len(mcp_standard_covered("project")))
            else:
                base = harness_label(harness)
            table.add_column(f"{base} {_INFO_GLYPH}", width=16)
        # State column — shows installed/library/unlisted (#360).
        table.add_column("State", width=10)
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
