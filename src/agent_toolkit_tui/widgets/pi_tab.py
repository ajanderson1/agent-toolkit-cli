"""Pi tab — Textual widget consuming `agent-toolkit-cli pi inventory --format json`.

Pure-data widget: receives records via constructor, exposes `rows()` for
testing without spinning up the whole Textual app. The app shells out to
``agent-toolkit-cli pi inventory --format json`` and passes the parsed
records into this widget for display.

Toggle key bindings (``u``/``p``) are intentionally not wired in this commit
— the spec ranks the read-only inventory view higher than toggle behaviour,
and a later commit can add them once the broader binding plumbing is in
place. See plan: docs/superpowers/plans/2026-05-19-pi-unified-extension-inventory.md.
"""
from __future__ import annotations

from typing import Any

from textual.widget import Widget
from textual.widgets import DataTable, Static


class PiTab(Widget):
    """Pi extension inventory display.

    Read-only for now — toggle bindings deferred to a follow-up commit.
    """

    def __init__(
        self,
        *,
        records: list[dict[str, Any]],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._records = records

    def rows(self) -> list[str]:
        """Plain-string rows for unit testing without the full Textual rig."""
        if not self._records:
            return []
        out: list[str] = []
        for r in self._records:
            badge = "1P" if r.get("origin") == "first-party" else "3P"
            out.append(
                f"{r.get('slug', ''):<24} {badge:<3} "
                f"{'✓' if r.get('user_loaded') else ' ':<3} "
                f"{'✓' if r.get('project_loaded') else ' ':<3} "
                f"{r.get('toolkit_intent', ''):<8} {r.get('source', '')}"
            )
        return out

    def compose(self):  # type: ignore[no-untyped-def]
        if not self._records:
            yield Static("(no Pi extensions found)")
            return
        table = DataTable(id="pi-tab-table")
        table.add_columns("Slug", "Origin", "U", "P", "Intent", "Source")
        for r in self._records:
            badge = "1P" if r.get("origin") == "first-party" else "3P"
            table.add_row(
                r.get("slug", ""),
                badge,
                "✓" if r.get("user_loaded") else " ",
                "✓" if r.get("project_loaded") else " ",
                r.get("toolkit_intent", ""),
                r.get("source", ""),
            )
        yield table
