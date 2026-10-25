"""Interactive DataTable for the TUI's skill tab.

Columns: Skill | Standard ⓘ | non-standard main harnesses ⓘ | State ⓘ | Source.

`space` toggles a cell (queues link/unlink in `_pending`).
`a` toggles a column. Clicking a glyphed header opens its column panel;
`i` always opens the selected skill's asset panel. Source stays passive.
`^s` Apply is handled by the App, which reads pending_entries().

The long tail of harnesses is managed via the CLI; the TUI grid only shows
the standard column plus the non-standard main harnesses derived from
`skills_nonstandard_main()` (currently Claude, Hermes, and Paperclip). The `Source`
column is passive (no toggle / no info popup); the SKILL slug-cell info
modal surfaces the skill description when present.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_toolkit_tui.asset_info import library_info, local_path_info, catalog_skill_info

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.message import Message
from textual.widgets import DataTable, Input
from textual.events import Resize
from rich.markup import escape
from rich.text import Text
from agent_toolkit_tui.widgets._support import adjust_source_column_width, current_source_column_width

from agent_toolkit_tui.column_info import get_column_info
from agent_toolkit_tui.display_names import (
    asset_type_label,
    harness_label,
    standard_column_header,
)
from agent_toolkit_tui.composition import skills_nonstandard_main
from agent_toolkit_tui.skill_state import SkillRow, SkillIntent
from agent_toolkit_tui.widgets._support import (
    adjust_source_column_width,
    set_source_column_width,
)
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal
from agent_toolkit_tui.widgets.filter_input import GridFilterInput

_STATE_MARKUP = {
    "clean":   "[green]clean[/]",
    "dirty":   "[yellow]dirty[/]",
    "missing": "[red]missing[/]",
    "copy":    "[blue]copy[/]",
    "catalog": "[cyan]catalog[/]",
    # "library" = in the library, not yet installed in this project. Normal
    # pre-install state. Rendered dim so it doesn't look alarming.
    "library": "[dim]library[/]",
    # "unlisted" = installed in this project but missing from the library
    # lock (#360). Functional; warning tint so it stands out from `library`.
    "unlisted": "[yellow]unlisted[/]",
}

_LINKED_GLYPH   = "[green]✔[/]"
_UNLINKED_GLYPH = "☐"
_PENDING_LINK   = "[yellow]+[/]"
_PENDING_UNLINK = "[yellow]-[/]"
_DRIFT_GLYPH    = "[red]![/]"
_STRAY_GLYPH    = "[yellow]?[/]"  # symlink exists but skill isn't installed here
_SKIPPED_GLYPH  = "[dim]●[/]"  # canonical-only, no symlink needed
_UNAVAIL_GLYPH  = "[dim]—[/]"  # harness not toggleable in this context
_INFO_GLYPH     = "ⓘ"
_GLOBAL_GLYPH   = "🌐"

Op = Literal["link", "unlink"]


class SkillGrid(Vertical):
    """One row per locked skill with selection-aware harness cells."""

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
        self._catalog_pending: dict[tuple[str, str, str], tuple] = {}
        self._skill_intents: dict[tuple[str, str, str], SkillIntent] = {}
        self._selection: tuple[str, ...] | None = None
        # Case-insensitive substring filter on slug (#249). "" = show all.
        self._filter: str = ""
        self._collapsed: set[tuple[str, str | None]] = set()

    def _active_agents(self) -> tuple[str, ...]:
        # Standard column + non-covered main harnesses. The long tail is
        # CLI-only (#351 post-demo decision).
        return ("standard",) + skills_nonstandard_main(self._selection)

    def set_harness_selection(self, selection: tuple[str, ...]) -> None:
        """Apply a presentation-only harness filter and rebuild columns."""
        self._selection = selection
        try:
            self._rebuild(self.query_one("#skill-table", DataTable))
        except Exception:
            pass

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def collection_count(self) -> int:
        return len({r.collection_key for r in self._rows if r.collection_key is not None})

    @property
    def row_slugs(self) -> list[str]:
        return [r.slug for r in self._rows]

    def set_rows(self, rows: list[SkillRow]) -> None:
        self._rows = sorted(rows, key=lambda r: r.slug)
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

    def pending_skill_intents(self) -> dict[tuple[str, str, str], SkillIntent]:
        return {key: value for key, value in self._skill_intents.items() if key in self._pending}

    def pending_catalog_entries(self) -> dict:
        return {key: value for key, value in self._catalog_pending.items() if self._pending.get(key) == "link"}

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
        rows = {r.slug: r for r in self._rows}
        for key, op in self._pending.items():
            row = rows.get(key[2])
            if row is not None and row.identity is not None:
                advertised = op == "link" and row.origin == "catalog"
                self._skill_intents.setdefault(key, SkillIntent(
                    row.identity,
                    row.catalog_url if advertised else None,
                    row.catalog_ref if advertised else None,
                    row.catalog_item if advertised else None,
                    frozenset(r.identity for r in self._rows if r.identity is not None and r.identity[:2] == row.identity[:2]),
                ))
            if op == "link" and row is not None and row.origin == "catalog" and row.catalog_item is not None:
                self._catalog_pending.setdefault(key, (row.catalog_url, row.catalog_item))
        self._catalog_pending = {key: value for key, value in self._catalog_pending.items() if self._pending.get(key) == "link"}
        self._skill_intents = {key: value for key, value in self._skill_intents.items() if key in self._pending}
        self.post_message(self.PendingChanged(len(self._pending)))

    def clear_pending(self) -> None:
        self._pending.clear()
        self._catalog_pending.clear()
        self._skill_intents.clear()
        try:
            table = self.query_one("#skill-table", DataTable)
            self._rebuild(table)
        except Exception:
            pass

    def restore_pending(self, pending: dict[tuple[str, str, str], Op], *, intents: dict[tuple[str, str, str], SkillIntent] | None = None) -> None:
        self._pending.update(pending)
        if intents is not None:
            self._skill_intents.update({key: value for key, value in intents.items() if key in pending})
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
        yield GridFilterInput(table_selector="#skill-table", id="skill-filter",
                              placeholder="Filter · parent affects ALL children · mixed − ≠ pending -")
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

    def _members(self, parent: SkillRow) -> list[SkillRow]:
        return [r for r in self._rows if r.collection_key == parent.collection_key]

    def _visible_rows(self) -> list[SkillRow]:
        visible = []
        seen = set()
        for row in self._rows:
            key = row.collection_key
            if key is None:
                if not self._filter or self._filter in row.slug.lower():
                    visible.append(row)
                continue
            if key in seen:
                continue
            seen.add(key)
            members = self._members(row)
            parent_match = self._filter in row.collection_label.lower()
            matching = [r for r in members if not self._filter or parent_match
                        or self._filter in (r.slug + ' ' + r.display_name).lower()]
            if not matching:
                continue
            repo_states = {r.repository_state for r in members if r.repository_state}
            repo_state = "dirty" if "dirty" in repo_states else "clean" if repo_states else None
            parent = SkillRow(
                slug=f"collection:{key!r}", source=row.source, ref=row.ref,
                state=repo_state or "clean", repository_state=repo_state,
                collection_key=key, collection_label=row.collection_label,
                display_name=row.collection_label, is_collection=True,
                collection_error=row.collection_error,
                description="Collection controls affect every child, including collapsed/filter-hidden skills. "
                            "Mixed (cyan −) means some selected; yellow - means pending removal. "
                            "Click the name or press Space/Enter there to expand/collapse. " + row.collection_error,
            )
            visible.append(parent)
            if key not in self._collapsed or self._filter:
                visible.extend(matching)
        return visible

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        self._toggle_at(event.coordinate)

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

    def on_resize(self, event: events.Resize) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        adjust_source_column_width(table, event, self._source_column_fixed_width())

    def action_toggle_cell(self) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        self._toggle_at(table.cursor_coordinate)

    def action_info(self) -> None:
        """Open the selected skill's asset panel, regardless of column (#479)."""
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen, asset_info_body

        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        visible = self._visible_rows()
        if table.cursor_coordinate.row >= len(visible):
            return
        row = visible[table.cursor_coordinate.row]
        from agent_toolkit_cli.paperclip_paths import normalize_skill_project_root
        from agent_toolkit_cli.skill_paths import canonical_skill_dir, library_skill_path

        if row.ref == "(untracked)":
            details = local_path_info(Path(row.source))
        elif row.origin == "catalog":
            details = ["Origin: catalog", "Not downloaded; nothing is exposed to a harness."]
        else:
            member = self._members(row)[0] if row.is_collection else row
            source_path = canonical_skill_dir(
                member.slug, scope=self._scope, home=Path.home(),
                project=normalize_skill_project_root(Path.cwd()) if self._scope == "project" else None,
            )
            if not source_path.exists():
                source_path = library_skill_path(member.slug)
            source_path = source_path.resolve()
            if row.is_collection and member.skill_path and member.skill_path != ".":
                for _ in Path(member.skill_path).parts:
                    source_path = source_path.parent
            details = library_info(source_path)
        if not row.is_collection and row.ref != "(untracked)":
            details += catalog_skill_info(row.slug, scope=self._scope, home=Path.home(), project=normalize_skill_project_root(Path.cwd()) if self._scope == "project" else None, item=row.catalog_item, catalog_url=row.catalog_url)
            if row.catalog_warning:
                details.append(escape(row.catalog_warning))
        self.app.push_screen(
            CellInfoScreen(
                title=f"{row.slug} · {asset_type_label('skill')}",
                body_markup=asset_info_body(
                    asset_label=asset_type_label("skill"),
                    slug=row.slug,
                    description=row.description,
                    description_location="SKILL.md",
                    source=escape(row.source),
                    ref=None if row.ref == "(untracked)" else row.ref,
                    state="local files (read-only)" if row.ref == "(untracked)" else row.state,
                    scope=self._scope,
                    extra_lines=details,
                ) + (f"\n\nSkill path: {row.skill_path}" if row.skill_path else ""),
            )
        )

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

        from agent_toolkit_cli.paperclip_paths import normalize_skill_project_root
        from agent_toolkit_cli.skill_paths import (
            agent_projection_dir,
            canonical_skill_dir,
        )

        if getattr(cell, "payload_missing", False):
            return "[red]Missing SKILL.md.[/]\nA matching directory or projection is not a usable skill without its document. Restore SKILL.md in the preserved checkout before retrying; no missing document is counted as a healthy selection."
        if getattr(cell, "exposure_reason", ""):
            return f"[yellow]Exposure uncertain.[/]\n{cell.exposure_reason}"
        if row.ref == "(untracked)":
            return "\n".join(local_path_info(Path(row.source)))
        # Unavailable cells (e.g. company-only Paperclip outside a company)
        # have no projection to describe; explain the context requirement
        # before any path resolver that would raise.
        if not getattr(cell, "available", True):
            return f"[dim]Unavailable.[/]\n{cell.unavailable_reason}"

        project_root = (
            None if scope == "global" else normalize_skill_project_root(Path.cwd())
        )
        canonical = canonical_skill_dir(
            row.slug,
            scope=scope,
            home=Path.home() if scope == "global" else None,
            project=project_root,
        )
        if agent == "standard":
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
            project=project_root,
        )
        if cell.skipped:
            return (
                f"Standard agent — no symlink needed.\n"
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
            if r.ref == "(untracked)" or cell is None or cell.skipped or not cell.available:
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
            if r.ref == "(untracked)" or cell is None or cell.skipped or not cell.available:
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

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Click a glyphed header to explain that column (#479 R1)."""
        key = self._column_key_for_index(event.column_index)
        if key is None:
            return
        self.app.push_screen(
            ColumnInfoModal(
                get_column_info(
                    key,
                    asset_type="skill",
                    context=self._context_for(
                        key=key,
                        row_index=event.data_table.cursor_coordinate.row,
                    ),
                )
            )
        )

    def _context_for(self, *, key: str, row_index: int) -> dict[str, object]:
        """Build live scope context for a column-info factory."""
        context: dict[str, object] = {"scope": self._scope}
        if key != "standard":
            return context
        context["global_linked"] = False
        visible = self._visible_rows()
        if 0 <= row_index < len(visible):
            global_cell = visible[row_index].cells.get(("standard", "global"))
            context["global_linked"] = bool(global_cell and global_cell.linked)
        return context

    def _toggle_at(self, coord: Coordinate) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return
        agent = self._agent_for_column(coord.column)
        # Cursor indexes the *visible* (filtered) rows, not the full set (#249).
        visible = self._visible_rows()
        if coord.row >= len(visible):
            return
        row = visible[coord.row]
        if row.is_collection:
            if coord.column == 0:
                if row.collection_key in self._collapsed:
                    self._collapsed.remove(row.collection_key)
                else:
                    self._collapsed.add(row.collection_key)
                self._rebuild(table)
                return
            if agent is None:
                return
            members = self._members(row)
            available = [r for r in members if r.ref != "(untracked)" and (c := r.cells.get((agent, self._scope)))
                         and c.available and not c.skipped]
            if not available:
                return
            all_selected = all(self._effective(r, agent) for r in available)
            target = not all_selected
            for member in available:
                key = (self._scope, agent, member.slug)
                if member.cells[(agent, self._scope)].linked == target:
                    self._pending.pop(key, None)
                else:
                    self._pending[key] = "link" if target else "unlink"
            self._rebuild(table)
            self._notify_pending()
            return
        if agent is None:
            return
        cell = row.cells.get((agent, self._scope))
        if row.ref == "(untracked)" or cell is None or cell.skipped or not cell.available:
            return
        # Standard at project scope is now a plain projection symlink into the
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
        # Layout: [0]=slug, [1..N]=_active_agents(), [N+1]=state, [N+2]=source.
        try:
            return 1 + self._active_agents().index(agent_name)
        except ValueError:
            return -1

    def _agent_for_column(self, col: int) -> str | None:
        active = self._active_agents()
        if 1 <= col <= len(active):
            return active[col - 1]
        return None

    def _column_key_for_index(self, col: int) -> str | None:
        """Resolve a column index to a COLUMN_INFO key.

        Layout: [0]=slug, [1..N]=_active_agents(), [N+1]=state, [N+2]=source.
        Returns None for unknown indices (cols 0 and N+2 — "slug" and
        "source" are not in the info registry today).
        """
        active = self._active_agents()
        n = len(active)
        if 1 <= col <= n:
            return active[col - 1]
        if col == n + 1:
            return "state"
        return None

    def on_resize(self, event: Resize) -> None:
        try:
            table = self.query_one("#skill-table", DataTable)
        except Exception:
            return

        # ID (20) + State (10) = 30. Plus agent cols (14 each).
        # We also account for padding in `adjust_source_column_width`
        fixed_width = self._source_column_fixed_width()
        adjust_source_column_width(table, event, fixed_width)

    def _rebuild(self, table: DataTable) -> None:
        saved = table.cursor_coordinate
        # Preserve the viewport: clear() resets scroll to the top, so a toggle
        # would jump the pane (#321). Save the offset and restore it below.
        # On the toggle path (cursor + rows unchanged) the restored cursor stays
        # inside the restored viewport, so Textual's deferred
        # `_scroll_cursor_into_view` (scheduled by the cursor-set after clear()
        # flags a dimension update) is a no-op and our offset holds. On a
        # content-shrinking rebuild (filter/scope) that deferred cursor-scroll
        # runs after this synchronous restore and lands the viewport around the
        # clamped cursor — acceptable (cursor stays visible), not the toggle case.
        saved_scroll = (table.scroll_x, table.scroll_y)
        source_width = current_source_column_width(table)
        table.clear(columns=True)
        # The asset column is explained by `i`, not header click (#479).
        table.add_column(asset_type_label("skill"), width=self._name_width())
        active = self._active_agents()
        standard_header = standard_column_header("skill", self._scope)
        assert standard_header is not None, "skills always have a standard slot"
        headers = {"standard": standard_header}
        for agent in active:
            # Every interactive agent column exposes either a column-info
            # modal (Standard) or per-cell info (e.g. Claude Code, Pi via
            # CellInfoScreen) — glyph them all. "standard" is the
            # load-bearing bundle key (v3.7 full rename, #350). The Standard
            # column leads; everything after it is implicitly non-standard
            # (group-tag header row removed per AJ demo feedback, #351).
            base = headers.get(agent, harness_label(agent))
            if agent == "standard" and self._harness_width() < 14:
                base = "Standard"
            table.add_column(f"{base} {_INFO_GLYPH}", width=self._harness_width())
        # State has a column-info modal → glyph it.
        table.add_column(f"State {_INFO_GLYPH}", width=10)
        # Source is passive — no info panel, no glyph.
        table.add_column("Source", width=source_width)
        self._adjust_source_column_width(table)
        visible = self._visible_rows()
        for row in visible:
            if row.is_collection:
                disclosure = "▸" if row.collection_key in self._collapsed else "▾"
                base = row.source.rsplit("/", 1)[-1]
                identities = {r.collection_key for r in self._rows if r.collection_key and r.source.rsplit("/", 1)[-1] == base}
                if len(identities) > 1:
                    base = f"{row.source}@{row.collection_key[1] or 'default'}"
                name = f"{disclosure} {base} · collection"
            else:
                name = ("  ↳ " if row.collection_key else "") + (row.display_name or row.slug)
            cells: list[str | Text] = [Text(name, no_wrap=True, overflow="ellipsis")]
            for agent in active:
                cells.append(self._cell_glyph(row=row, agent=agent))
            cells.append("collection" if row.is_collection and row.repository_state is None else "[dim]local[/]" if row.ref == "(untracked)" else _STATE_MARKUP.get(row.state, row.state))
            origin = "local" if row.ref == "(untracked)" else row.origin
            source = row.collection_label if row.is_collection else row.source
            cells.append(Text(f"{origin} · {source}", no_wrap=True, overflow="ellipsis"))
            table.add_row(*cells, key=f"skill:{row.slug}")
        if visible:
            max_row = len(visible) - 1
            # Layout: slug + N agent cols + state + source.
            max_col = 2 + len(active)
            table.cursor_coordinate = Coordinate(
                row=min(saved.row, max_row),
                column=min(saved.column, max_col),
            )
        # Pin the viewport back (clamped by Textual to the new content range).
        table.scroll_to(
            x=saved_scroll[0], y=saved_scroll[1], animate=False, force=True
        )

    def _source_column_fixed_width(self) -> int:
        return self._name_width() + (self._harness_width() * len(self._active_agents())) + 10

    def _adjust_source_column_width(self, table: DataTable) -> None:
        if self.size.width > 0:
            set_source_column_width(
                table,
                self.size.width,
                self._source_column_fixed_width(),
            )

    def _harness_width(self) -> int:
        return 11 if self.collection_count and self.size.width < 120 else 14

    def _name_width(self) -> int:
        if not self.collection_count:
            return 20
        longest = max((len(r.display_name or r.slug) + 2 for r in self._rows), default=26)
        return min(40, max(28, longest))

    def _effective(self, row: SkillRow, agent: str) -> bool:
        cell = row.cells.get((agent, self._scope))
        if cell is None or not cell.available or cell.drift or cell.stray or cell.exposure_reason or row.state == "missing":
            return False
        pending = self._pending.get((self._scope, agent, row.slug))
        return pending == "link" or (cell.linked and pending != "unlink")

    def _cell_glyph(self, *, row: SkillRow, agent: str) -> str:
        if row.is_collection:
            if row.collection_error:
                return _DRIFT_GLYPH
            members = self._members(row)
            cells = [r.cells.get((agent, self._scope)) for r in members]
            if not any(c and c.available for c in cells):
                return _UNAVAIL_GLYPH
            if any(c and (c.drift or c.stray or c.exposure_reason) for c in cells) or any(r.state == "missing" for r in members):
                return _DRIFT_GLYPH
            n = sum(self._effective(r, agent) for r in members)
            return _LINKED_GLYPH if n == len(members) else ("[cyan]−[/]" if n else _UNLINKED_GLYPH)
        cell = row.cells.get((agent, self._scope))
        if cell is None:
            base = " "
        elif not cell.available:
            base = _UNAVAIL_GLYPH
        elif cell.payload_missing:
            base = _DRIFT_GLYPH
        elif cell.exposure_reason:
            base = "[yellow]?[/]"
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
