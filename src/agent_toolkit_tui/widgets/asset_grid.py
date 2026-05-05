"""Main grid — rows = assets of current kind, cols = visible harnesses."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input

from agent_toolkit_tui.messages import AssetToggled
from agent_toolkit_tui.state import AssetRow, CellState, InventoryState

_GLYPH = {
    "linked":                     "✔",
    "unlinked":                   "☐",
    "unsupported":                "──",
    "broken":                     "⚠ ",
    "linked-matches":             "✔",
    "linked-drifted":             "≁",
    "unlinked-allowlisted":       "☐",
    "installed-not-allowlisted":  "!",
}

# Pending overlay: same shape as the *target* state, colored to signal
# "queued, not yet applied". Rich markup runs through DataTable cells, but
# Textual CSS vars like $warning aren't resolved there — use a literal color.
_PENDING_LINK   = "[yellow]✔[/]"
_PENDING_UNLINK = "[yellow]☐[/]"


class AssetGrid(Vertical):
    """One row per asset, one column per visible harness, per current scope."""

    DEFAULT_CSS = """
    AssetGrid { border: round $primary; }
    AssetGrid Input#grid-filter { height: 3; border: round $primary 30%; margin: 0 1 1 1; }
    AssetGrid DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("space", "toggle_cell", "Toggle", priority=True),
        Binding("a", "toggle_column", "All/None", priority=True),
    ]

    def __init__(self, state: InventoryState, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._state = state
        self._kind = "skill"
        self._scope = "project"
        self._visible_harnesses = list(state.all_harnesses)
        self._pending: dict[tuple[str, str, str, str], str] = {}   # (scope,harness,kind,slug) -> op
        self._filter: str = ""

    def compose(self) -> ComposeResult:
        yield Input(placeholder="filter…", id="grid-filter")
        yield DataTable(id="grid-table", cursor_type="cell", zebra_stripes=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "grid-filter":
            self._filter = event.value.strip().lower()
            self._rebuild()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "grid-filter":
            self.query_one("#grid-table", DataTable).focus()

    def on_mount(self) -> None:
        self._rebuild()

    # ----- public API ------------------------------------------------------
    def set_kind(self, kind: str) -> None:
        self._kind = kind
        self._rebuild()

    def set_scope(self, scope: str) -> None:
        self._scope = scope
        self._rebuild()

    def update_state(self, state: InventoryState) -> None:
        self._state = state
        # Drop pending entries that have been satisfied by the new ground truth.
        self._pending = {k: v for k, v in self._pending.items()
                         if not self._matches_state(k, v)}
        self._rebuild()

    def pending_entries(self) -> dict[tuple[str, str, str, str], str]:
        return dict(self._pending)

    def clear_pending(self) -> None:
        self._pending.clear()
        self._rebuild()

    # ----- key bindings -----------------------------------------------------
    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        self._toggle_at(event.coordinate)

    def action_toggle_cell(self) -> None:
        try:
            table = self.query_one("#grid-table", DataTable)
        except Exception:
            return
        self._toggle_at(table.cursor_coordinate)

    def action_toggle_column(self) -> None:
        try:
            table = self.query_one("#grid-table", DataTable)
        except Exception:
            return
        col = table.cursor_coordinate.column
        if col == 0 or col - 1 >= len(self._visible_harnesses):
            return
        harness = self._visible_harnesses[col - 1]
        rows = self._rows_for_kind()

        # Decide direction: if any visible+supported cell would still be
        # "off" after pending ops, link-all; otherwise unlink-all.
        any_off = False
        for row in rows:
            cell = row.cells.get((harness, self._scope))
            if cell is None or cell.status in {"unsupported", "installed-not-allowlisted"}:
                continue
            key = (self._scope, harness, row.kind, row.slug)
            pending = self._pending.get(key)
            _is_linked = cell.status in {"linked", "linked-matches", "linked-drifted"}
            effective_linked = (
                (_is_linked and pending != "unlink")
                or pending == "link"
            )
            if not effective_linked:
                any_off = True
                break
        target_op = "link" if any_off else "unlink"

        for row in rows:
            cell = row.cells.get((harness, self._scope))
            if cell is None or cell.status in {"unsupported", "installed-not-allowlisted"}:
                continue
            key = (self._scope, harness, row.kind, row.slug)
            pending = self._pending.get(key)
            _is_linked = cell.status in {"linked", "linked-matches", "linked-drifted"}
            already = (
                (_is_linked and pending != "unlink")
                or pending == "link"
            ) if target_op == "link" else (
                (not _is_linked and pending != "link")
                or pending == "unlink"
            )
            if already:
                # Cell already in target state — drop any pending inverse.
                if pending and pending != target_op:
                    del self._pending[key]
                continue
            # Need to flip. If ground truth already matches, just clear pending.
            ground_matches = (
                (target_op == "link" and _is_linked)
                or (target_op == "unlink" and not _is_linked)
            )
            if ground_matches:
                if pending:
                    del self._pending[key]
                continue
            self._pending[key] = target_op
            self.post_message(AssetToggled(
                kind=row.kind, slug=row.slug,
                harness=harness, scope=self._scope, op=target_op,
            ))
        self._rebuild()

    def _toggle_at(self, coord: Coordinate) -> None:
        # Column 0 = slug; columns 1..N = harnesses in self._visible_harnesses.
        col = coord.column
        if col == 0 or col - 1 >= len(self._visible_harnesses):
            return
        harness = self._visible_harnesses[col - 1]
        rows = self._rows_for_kind()
        if coord.row >= len(rows):
            return
        row = rows[coord.row]
        cell = row.cells.get((harness, self._scope))
        if cell is None or cell.status in {"unsupported", "installed-not-allowlisted"}:
            return
        key = (self._scope, harness, row.kind, row.slug)
        # If there's already a pending op on this cell, toggle it OFF — restore
        # ground truth. Otherwise queue the inverse of the current status.
        if key in self._pending:
            del self._pending[key]
            op = "clear"
        else:
            _is_linked = cell.status in {"linked", "linked-matches", "linked-drifted"}
            op = "unlink" if _is_linked else "link"
            self._pending[key] = op
        self.post_message(AssetToggled(kind=row.kind, slug=row.slug,
                                       harness=harness, scope=self._scope, op=op))
        self._rebuild()

    # ----- internals --------------------------------------------------------
    def _rows_for_kind(self) -> list[AssetRow]:
        rows = [r for r in self._state.rows if r.kind == self._kind]
        if self._filter:
            rows = [r for r in rows if self._filter in r.slug.lower()]
        return rows

    def _rebuild(self) -> None:
        try:
            table = self.query_one("#grid-table", DataTable)
        except Exception:
            return
        saved_cursor = table.cursor_coordinate
        table.clear(columns=True)
        table.add_column(self._kind.upper(), width=32)
        for h in self._visible_harnesses:
            table.add_column(h, width=8)
        rows = self._rows_for_kind()
        seen_keys: set[str] = set()
        for row in rows:
            cells = [row.slug]
            for h in self._visible_harnesses:
                cell = row.cells.get((h, self._scope))
                glyph = _GLYPH.get(cell.status, "  ") if cell else "  "
                pending = self._pending.get((self._scope, h, row.kind, row.slug))
                if pending == "link":
                    glyph = _PENDING_LINK
                elif pending == "unlink":
                    glyph = _PENDING_UNLINK
                cells.append(glyph)
            # Schema allows duplicate (kind, slug) pairs at distinct paths
            # (see commands/aj/journal/* vs commands/custom_commands/*). Use
            # the asset path to disambiguate the row key so DataTable doesn't
            # raise DuplicateKey.
            key = f"{row.kind}:{row.slug}:{row.path}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            table.add_row(*cells, key=key)
        if rows:
            max_row = len(rows) - 1
            max_col = len(self._visible_harnesses)  # slug + N harness cols
            table.cursor_coordinate = Coordinate(
                row=min(saved_cursor.row, max_row),
                column=min(saved_cursor.column, max_col),
            )

    def _matches_state(self, key: tuple[str, str, str, str], op: str) -> bool:
        scope, harness, kind, slug = key
        for r in self._state.rows:
            if r.kind == kind and r.slug == slug:
                cell = r.cells.get((harness, scope))
                if cell is None:
                    return True   # cell vanished — pending is moot
                if op == "link" and cell.status in {"linked", "linked-matches", "linked-drifted"}:
                    return True
                if op == "unlink" and cell.status in {
                    "unlinked", "unsupported", "unlinked-allowlisted", "installed-not-allowlisted",
                }:
                    return True
        return False
