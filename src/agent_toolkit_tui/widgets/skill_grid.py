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

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import DataTable, Input

from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_tui.column_info import COLUMN_INFO, get_column_info
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
_STRAY_GLYPH    = "[yellow]?[/]"  # symlink exists but skill isn't installed here
_SKIPPED_GLYPH  = "[dim]●[/]"  # canonical-only, no symlink needed
_INFO_GLYPH     = "ⓘ"
_GLOBAL_GLYPH   = "🌐"

Op = Literal["link", "unlink"]


class FilterInput(Input):
    """Filter box that hands focus to the skill table on Down / Tab.

    Down-arrow and Tab are the "I'm done typing, let me pick a skill" gesture
    (#249). We intercept them here and move focus into the sibling
    `#skill-table` DataTable, stopping the event so Tab does not run Textual's
    default focus-cycle and Down does not get swallowed as a no-op cursor
    move inside the (single-line) input. Every other key — including printable
    characters that happen to match an App binding like `s`/`q` — falls
    through to the Input's normal handling.
    """

    def on_key(self, event: events.Key) -> None:
        if event.key in ("down", "tab"):
            try:
                self.screen.query_one("#skill-table", DataTable).focus()
            except NoMatches:
                # No table to hand focus to (not mounted yet) — let the key
                # fall through to the Input's default handling rather than
                # swallowing it.
                return
            event.stop()
            event.prevent_default()


class SkillGrid(Vertical):
    """One row per locked skill; interactive cells for INTERACTIVE_AGENTS."""

    class PendingChanged(Message):
        """Posted whenever the pending toggle set changes.

        Carries the current pending count so the App can refresh the footer
        "Pending: N" label live as the user toggles cells. The App owns the
        footer text; the grid just announces the count.
        """

        def __init__(self, count: int) -> None:
            super().__init__()
            self.count = count

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
        # Case-insensitive substring filter on slug (#249). "" = show all.
        self._filter: str = ""

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

    def _notify_pending(self) -> None:
        """Announce the current pending count so the App can refresh the footer.

        Posted from the user-driven toggle paths (`_toggle_at`,
        `action_toggle_column`) — the cases where the count changes from inside
        the widget and the App would otherwise never learn about it. The App's
        own mutators (clear_pending / restore_pending / set_rows / set_scope)
        deliberately do **not** notify: their callers already set the footer
        line explicitly (e.g. the "applied: N ok" / "reverted" summaries), and a
        message here would clobber that summary on the next event-loop turn.
        Posting a message is safe even before mount (Textual queues it).
        """
        self.post_message(self.PendingChanged(len(self._pending)))

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
        # The table only renders visible rows, so the cursor row index must be
        # the slug's position in the *visible* list, not the full set (#249).
        visible_slugs = [r.slug for r in self._visible_rows()]
        try:
            row_idx = visible_slugs.index(row_slug)
        except ValueError:
            return
        table.cursor_coordinate = Coordinate(row=row_idx, column=col_idx)
        # Positioning the cursor is a "navigate here to act on it" gesture, so
        # take focus to the table — otherwise the filter Input (focused on open
        # since #249) would swallow the next keypress (space/`i`) as text.
        table.focus()

    def compose(self) -> ComposeResult:
        # Filter box on top, table below — mirrors the v1 layout (#249).
        yield FilterInput(placeholder="filter…", id="skill-filter")
        table = DataTable(id="skill-table", cursor_type="cell", zebra_stripes=True)
        yield table

    # ----- filter ---------------------------------------------------------
    def set_filter(self, text: str) -> None:
        """Set the case-insensitive substring filter and rebuild the table."""
        self._filter = text.strip().lower()
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        self._rebuild(table)

    def _visible_rows(self) -> list[SkillRow]:
        """Rows after applying the active filter (case-insensitive substring).

        The filter is purely a view over `self._rows`: it never changes the
        full row set, the pending toggle state, or the apply/status math —
        only what the table renders and what the cursor can land on.
        """
        if self._filter:
            return [r for r in self._rows if self._filter in r.slug.lower()]
        return list(self._rows)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "skill-filter":
            self.set_filter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Enter in the filter box is a convenience escape into the table.
        if event.input.id == "skill-filter":
            try:
                self.query_one("#skill-table", DataTable).focus()
            except Exception:
                pass

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
        # Cursor indexes the *visible* (filtered) rows, not the full set (#249).
        visible = self._visible_rows()
        if coord.row >= len(visible):
            return

        # Column-level info first: defer to ColumnInfoModal for registered keys.
        # Use COLUMN_INFO membership directly so the factory isn't called twice
        # (action_open_column_info calls it with context to build the real modal).
        col_key = self._column_key_for_index(coord.column)
        if col_key is not None and col_key in COLUMN_INFO:
            self.action_open_column_info()
            return

        row = visible[coord.row]
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
                f"General agent — no symlink needed.\n"
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
        if cell.stray:
            try:
                target = link.readlink()
            except OSError:
                target = "(unreadable)"
            return (
                f"[yellow]Stray symlink.[/]\n\n"
                f"Symlink: {link}\n"
                f"Points to: {target}\n\n"
                f"This skill isn't installed at {scope} scope, so the link\n"
                f"has no canonical to point at. Remove it:\n"
                f"  [b]rm {link}[/]\n\n"
                f"Or scan + clean all stray links:\n"
                f"  [b]agent-toolkit-cli skill doctor {scope_flag}[/]"
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
        self._notify_pending()

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
        # row_index comes from the table cursor → index the visible rows (#249).
        visible = self._visible_rows()
        if row_index < 0 or row_index >= len(visible):
            return None
        row = visible[row_index]
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
        # Cursor indexes the *visible* (filtered) rows, not the full set (#249).
        visible = self._visible_rows()
        if coord.row >= len(visible):
            return
        row = visible[coord.row]
        cell = row.cells.get((agent, self._scope))
        if cell is None or cell.skipped:
            return
        # Universal at project scope is now a plain projection symlink into the
        # external store (post-#235/#237), so unlinking it is non-destructive and
        # the engine handles it like any other cell — no special guard (#232).
        key = (self._scope, agent, row.slug)
        if key in self._pending:
            del self._pending[key]
        else:
            self._pending[key] = "unlink" if cell.linked else "link"
        self._rebuild(table)
        self._notify_pending()

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
        # Preserve the viewport: clear() resets scroll to the top, so a toggle
        # would jump the pane (#321). Save the offset and restore it after the
        # cursor is set (cursor-set can auto-scroll; restoring last wins).
        saved_scroll = (table.scroll_x, table.scroll_y)
        table.clear(columns=True)
        # Slug column has cell-info (the slug-cell panel) → glyph it.
        table.add_column(f"SKILL {_INFO_GLYPH}", width=20)
        for agent in INTERACTIVE_AGENTS:
            # Every interactive agent column exposes either a column-info
            # modal (General) or per-cell info (Claude Code, Pi via
            # CellInfoScreen) — glyph them all. The "universal" token is the
            # load-bearing bundle key; only its display label is "General"
            # (v3 universal→general rename, #304 bug 3).
            base = "General" if agent == "universal" else AGENTS[agent].display_name
            table.add_column(f"{base} {_INFO_GLYPH}", width=14)
        # State has a column-info modal → glyph it.
        table.add_column(f"State {_INFO_GLYPH}", width=10)
        # Source is passive — no info panel, no glyph.
        table.add_column("Source", width=30)
        visible = self._visible_rows()
        for row in visible:
            cells: list[str] = [row.slug]
            for agent in INTERACTIVE_AGENTS:
                cells.append(self._cell_glyph(row=row, agent=agent))
            cells.append(_STATE_MARKUP.get(row.state, row.state))
            cells.append(row.source)
            table.add_row(*cells, key=f"skill:{row.slug}")
        if visible:
            max_row = len(visible) - 1
            # Layout: slug + N agent cols + state + source.
            max_col = 2 + len(INTERACTIVE_AGENTS)
            table.cursor_coordinate = Coordinate(
                row=min(saved.row, max_row),
                column=min(saved.column, max_col),
            )
        # Pin the viewport back (clamped by Textual to the new content range).
        table.scroll_to(
            x=saved_scroll[0], y=saved_scroll[1], animate=False, force=True
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
            elif cell.stray:
                base = _STRAY_GLYPH
            else:
                base = _LINKED_GLYPH if cell.linked else _UNLINKED_GLYPH
        if self._scope == "project":
            global_cell = row.cells.get((agent, "global"))
            if (
                global_cell is not None
                and global_cell.linked
                and not global_cell.drift
                and not global_cell.stray
                and not global_cell.skipped
            ):
                return f"{base} {_GLOBAL_GLYPH}"
        return base
