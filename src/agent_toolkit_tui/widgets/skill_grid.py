"""Interactive DataTable for the TUI's skill tab.

Columns: SKILL ⓘ | Universal ⓘ | Claude Code ⓘ | Pi ⓘ | State ⓘ | Source.

`space` toggles a cell (queues link/unlink in `_pending`).
`a` toggles a column.
`i` opens ColumnInfoModal for columns with registered info (Universal, State); for all other glyphed columns (SKILL, Claude Code, Pi) it opens CellInfoScreen with per-cell or slug context. The Source column has no info panel.
`^s` Apply is handled by the App, which reads pending_entries().

The long tail of agents is managed via the CLI; the TUI grid only shows
the interactive shortlist (universal + claude-code + pi). The `Source`
column is passive (no toggle / no info popup); the SKILL slug-cell info
modal surfaces the skill description when present.
"""
from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillRow
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal

_STATE_MARKUP = {
    "clean":   "[green]clean[/]",
    "dirty":   "[yellow]dirty[/]",
    "missing": "[red]missing[/]",
    "copy":    "[blue]copy[/]",
    # "library" = in the library, not yet installed in this project. Normal
    # pre-install state. Rendered dim so it doesn't look alarming.
    "library": "[dim]library[/]",
}

_LINKED_GLYPH   = "[green]✔[/]"
_UNLINKED_GLYPH = "☐"
_PENDING_LINK   = "[yellow]+[/]"
_PENDING_UNLINK = "[yellow]-[/]"
_DRIFT_GLYPH    = "[red]![/]"
_SKIPPED_GLYPH  = "[dim]●[/]"  # canonical-only, no symlink needed
_INFO_GLYPH     = "ⓘ"
_GLOBAL_GLYPH   = "🌐"

Op = Literal["link", "unlink"]


class SkillGrid(Vertical):
    """One row per locked skill; interactive cells for INTERACTIVE_AGENTS."""

    DEFAULT_CSS = """
    SkillGrid { border: round $primary; }
    SkillGrid DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("space", "toggle_cell", "Toggle", priority=True),
        Binding("a", "toggle_column", "All/None", priority=True),
        Binding("i", "info", "Info", priority=True),
    ]

    def __init__(self, rows: list[SkillRow], *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._rows = sorted(rows, key=lambda r: r.slug)
        self._scope: Literal["global", "project"] = "global"
        # (scope, agent_name, slug) -> op
        self._pending: dict[tuple[str, str, str], Op] = {}

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def row_slugs(self) -> list[str]:
        return [r.slug for r in self._rows]

    def set_rows(self, rows: list[SkillRow]) -> None:
        self._rows = sorted(rows, key=lambda r: r.slug)
        self._pending.clear()
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        self._rebuild(table)

    def set_scope(self, scope: Literal["global", "project"]) -> None:
        self._scope = scope
        self._pending.clear()

    def pending_entries(self) -> dict[tuple[str, str, str], Op]:
        return dict(self._pending)

    def clear_pending(self) -> None:
        self._pending.clear()
        try:
            table = self.query_one("#skill-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def restore_pending(self, pending: dict[tuple[str, str, str], Op]) -> None:
        self._pending.update(pending)
        try:
            table = self.query_one("#skill-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def cursor_to_cell(self, *, row_slug: str, agent_name: str) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        col_idx = self._column_index(agent_name)
        try:
            row_idx = self.row_slugs.index(row_slug)
        except ValueError:
            return
        table.cursor_coordinate = Coordinate(row=row_idx, column=col_idx)

    def compose(self) -> ComposeResult:
        table = DataTable(id="skill-table", cursor_type="cell", zebra_stripes=True)
        yield table

    def on_mount(self) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def action_toggle_cell(self) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        self._toggle_at(table.cursor_coordinate)

    def action_info(self) -> None:
        """Route `i` by column. Columns with a registered ColumnInfo open
        ColumnInfoModal (header-level info such as Universal bundle, State
        badge legend). Everything else opens CellInfoScreen with the per-cell
        state (linked target, drift+doctor command, pending op, slug source)."""
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen

        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        coord = table.cursor_coordinate
        if coord.row >= len(self._rows):
            return

        # Column-level info first: defer to ColumnInfoModal for registered keys.
        col_key = self._column_key_for_index(coord.column)
        if col_key is not None and get_column_info(col_key) is not None:
            self.action_open_column_info()
            return

        row = self._rows[coord.row]
        scope = self._scope
        scope_flag = "-g" if scope == "global" else "-p"

        # Slug column → source/ref/state context.
        if coord.column == 0:
            # 'library' = no meaningful state (slug in library, not yet
            # installed here). Render as em-dash so the modal doesn't look
            # like it's printing a debug literal.
            state_display = "—" if row.state == "library" else row.state
            title = f"{row.slug} · slug"
            body = (
                f"Skill [b]{row.slug}[/]\n"
                f"Source: {row.source}\n"
                f"Ref:    {row.ref}\n"
                f"State:  {state_display}"
            )
            if row.description:
                body += f"\n\nDescription:\n{row.description}"
        else:
            # Agent column without registered info (e.g. Claude Code, Pi) — cell-state body.
            agent = self._agent_for_column(coord.column)
            if agent is None:
                return
            cell = row.cells.get((agent, scope))
            if cell is None:
                return
            title = f"{row.slug} · {agent} @ {scope}"
            pending = self._pending.get((scope, agent, row.slug))
            body = self._info_body_for_cell(
                row=row,
                agent=agent,
                cell=cell,
                pending=pending,
                scope=scope,
                scope_flag=scope_flag,
            )
        self.app.push_screen(CellInfoScreen(title=title, body_markup=body))

    def _info_body_for_cell(
        self,
        *,
        row: "SkillRow",
        agent: str,
        cell: object,
        pending: "str | None",
        scope: str,
        scope_flag: str,
    ) -> str:
        from pathlib import Path

        from agent_toolkit_cli.skill_paths import (
            agent_projection_dir,
            canonical_skill_dir,
        )

        canonical = canonical_skill_dir(
            row.slug,
            scope=scope,
            home=Path.home() if scope == "global" else None,
            project=None if scope == "global" else Path.cwd(),
        )
        if agent == "universal":
            if scope == "global":
                bundle = Path.home() / ".agents" / "skills" / row.slug
                if cell.drift:
                    return (
                        f"[red]Drift detected.[/]\n\n"
                        f"Bundle path: {bundle}\n"
                        f"Expected:    symlink → {canonical}\n\n"
                        f"Fix with:\n"
                        f"  [b]agent-toolkit-cli skill doctor {row.slug} "
                        f"{scope_flag}[/]"
                    )
                if cell.linked:
                    return f"Linked.\nBundle: {bundle} → {canonical}"
                return (
                    f"Not linked.\nPress [b]space[/] to queue link "
                    f"({bundle} → {canonical})."
                )
            # project scope: canonical IS the install
            if cell.linked:
                return f"Project canonical exists at {canonical}."
            return (
                f"Not installed in project.\nPress [b]space[/] to queue "
                f"install (clones into {canonical})."
            )

        link = agent_projection_dir(
            agent,
            row.slug,
            scope=scope,
            home=Path.home() if scope == "global" else None,
            project=None if scope == "global" else Path.cwd(),
        )
        if cell.skipped:
            return (
                f"Universal agent — no symlink needed.\n"
                f"Skill lives at {canonical}."
            )
        if pending == "link":
            return (
                f"[yellow]Pending: link.[/]\n"
                f"{link} → {canonical}\n\n"
                f"Press [b]^s[/] to apply."
            )
        if pending == "unlink":
            return (
                f"[yellow]Pending: unlink.[/]\n"
                f"{link}\n\n"
                f"Press [b]^s[/] to apply."
            )
        if cell.drift:
            try:
                target = link.resolve()
            except OSError:
                target = "(unreadable)"
            return (
                f"[red]Drift detected.[/]\n\n"
                f"Symlink: {link}\n"
                f"Points to: {target}\n"
                f"Expected:  {canonical}\n\n"
                f"Fix with:\n"
                f"  [b]agent-toolkit-cli skill doctor {row.slug} {scope_flag}[/]"
            )
        if cell.linked:
            return f"Linked.\n{link} → {canonical}"
        return (
            f"Not linked.\nPress [b]space[/] to queue link "
            f"({link} → {canonical})."
        )

    def action_toggle_column(self) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        col = table.cursor_coordinate.column
        agent = self._agent_for_column(col)
        if agent is None:
            return
        scope = self._scope
        any_off = False
        for r in self._rows:
            cell = r.cells.get((agent, scope))
            if cell is None or cell.skipped:
                continue
            key = (scope, agent, r.slug)
            pending = self._pending.get(key)
            effective_linked = (
                (cell.linked and pending != "unlink") or pending == "link"
            )
            if not effective_linked:
                any_off = True
                break
        target_op: Op = "link" if any_off else "unlink"
        for r in self._rows:
            cell = r.cells.get((agent, scope))
            if cell is None or cell.skipped:
                continue
            key = (scope, agent, r.slug)
            ground_matches = (
                (target_op == "link" and cell.linked)
                or (target_op == "unlink" and not cell.linked)
            )
            if ground_matches:
                self._pending.pop(key, None)
                continue
            self._pending[key] = target_op
        self._rebuild(table)

    def action_open_column_info(self) -> None:
        """Open ColumnInfoModal for the column under the cursor, if registered."""
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        col = table.cursor_coordinate.column
        key = self._column_key_for_index(col)
        if key is None:
            return
        context = self._context_for(key=key, row_index=table.cursor_coordinate.row)
        info = get_column_info(key, context=context)
        if info is None:
            return
        self.app.push_screen(ColumnInfoModal(info))

    def _context_for(self, *, key: str, row_index: int) -> dict | None:
        """Build the per-call context dict for get_column_info().

        Today only the 'universal' key uses it: we surface whether the focused
        row is also installed globally so the modal can omit the 🌐 paragraph
        when it's not.
        """
        if key != "universal":
            return None
        if row_index < 0 or row_index >= len(self._rows):
            return None
        row = self._rows[row_index]
        global_cell = row.cells.get(("universal", "global"))
        return {"global_linked": bool(global_cell and global_cell.linked)}

    def _toggle_at(self, coord: Coordinate) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        agent = self._agent_for_column(coord.column)
        if agent is None:
            return
        if coord.row >= len(self._rows):
            return
        row = self._rows[coord.row]
        cell = row.cells.get((agent, self._scope))
        if cell is None or cell.skipped:
            return
        # Refuse destructive project-scope universal unlinks from the TUI.
        # Removing the project canonical (<project>/.agents/skills/<slug>/)
        # is a destructive operation that should be done explicitly via
        # `skill remove --scope project`, not from a cell click.
        # TODO: surface a user-visible message here (e.g. self.app.notify())
        # once a notify pattern is established for SkillGrid.
        if agent == "universal" and self._scope == "project" and cell.linked:
            return
        key = (self._scope, agent, row.slug)
        if key in self._pending:
            del self._pending[key]
        else:
            self._pending[key] = "unlink" if cell.linked else "link"
        self._rebuild(table)

    def _column_index(self, agent_name: str) -> int:
        # Layout: [0]=slug, [1..N]=INTERACTIVE_AGENTS, [N+1]=state, [N+2]=source.
        try:
            return 1 + list(INTERACTIVE_AGENTS).index(agent_name)
        except ValueError:
            return -1

    def _agent_for_column(self, col: int) -> str | None:
        if col < 1:
            return None
        idx = col - 1
        if 0 <= idx < len(INTERACTIVE_AGENTS):
            return INTERACTIVE_AGENTS[idx]
        return None

    def _column_key_for_index(self, col: int) -> str | None:
        """Resolve a column index to a COLUMN_INFO key.

        Layout: [0]=slug, [1..N]=INTERACTIVE_AGENTS, [N+1]=state, [N+2]=source.
        Returns None for unknown indices (cols 0 and N+2 — "slug" and
        "source" are not in the info registry today).
        """
        n = len(INTERACTIVE_AGENTS)
        if 1 <= col <= n:
            return INTERACTIVE_AGENTS[col - 1]
        if col == n + 1:
            return "state"
        return None

    def _rebuild(self, table: DataTable) -> None:
        saved = table.cursor_coordinate
        table.clear(columns=True)
        # Slug column has cell-info (the slug-cell panel) → glyph it.
        table.add_column(f"SKILL {_INFO_GLYPH}", width=20)
        for agent in INTERACTIVE_AGENTS:
            # Every interactive agent column exposes either a column-info
            # modal (Universal) or per-cell info (Claude Code, Pi via
            # CellInfoScreen) — glyph them all.
            base = "Universal" if agent == "universal" else AGENTS[agent].display_name
            table.add_column(f"{base} {_INFO_GLYPH}", width=14)
        # State has a column-info modal → glyph it.
        table.add_column(f"State {_INFO_GLYPH}", width=10)
        # Source is passive — no info panel, no glyph.
        table.add_column("Source", width=30)
        for row in self._rows:
            cells: list[str] = [row.slug]
            for agent in INTERACTIVE_AGENTS:
                cells.append(self._cell_glyph(row=row, agent=agent))
            cells.append(_STATE_MARKUP.get(row.state, row.state))
            cells.append(row.source)
            table.add_row(*cells, key=f"skill:{row.slug}")
        if self._rows:
            max_row = len(self._rows) - 1
            # Layout: slug + N agent cols + state + source.
            max_col = 2 + len(INTERACTIVE_AGENTS)
            table.cursor_coordinate = Coordinate(
                row=min(saved.row, max_row),
                column=min(saved.column, max_col),
            )

    def _cell_glyph(self, *, row: SkillRow, agent: str) -> str:
        cell = row.cells.get((agent, self._scope))
        if cell is None:
            base = " "
        elif cell.skipped:
            base = _SKIPPED_GLYPH
        else:
            pending = self._pending.get((self._scope, agent, row.slug))
            if pending == "link":
                base = _PENDING_LINK
            elif pending == "unlink":
                base = _PENDING_UNLINK
            elif cell.drift:
                base = _DRIFT_GLYPH
            else:
                base = _LINKED_GLYPH if cell.linked else _UNLINKED_GLYPH
        if self._scope == "project":
            global_cell = row.cells.get((agent, "global"))
            if (
                global_cell is not None
                and global_cell.linked
                and not global_cell.drift
                and not global_cell.skipped
            ):
                return f"{base} {_GLOBAL_GLYPH}"
        return base
