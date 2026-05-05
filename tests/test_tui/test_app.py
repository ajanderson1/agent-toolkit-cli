"""Integration tests via textual.pilot.

These do NOT shell out — they use a FakeRunner that mimics the real CLI's
JSON shape and records calls.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.runner import PlanResult


class FakeRunner:
    def __init__(self, doc: dict):
        self.doc = doc
        self.calls: list[tuple] = []
        self.list_calls: int = 0

    def list_state(self) -> dict:
        self.list_calls += 1
        return self.doc

    def link_plan(self, *, scope, harness, entries, dry_run=False):
        self.calls.append(("link", scope, harness, entries, dry_run))
        # Pretend everything succeeds
        return PlanResult(ok=len(entries), failed=0)

    def unlink_plan(self, *, scope, harness, entries, dry_run=False):
        self.calls.append(("unlink", scope, harness, entries, dry_run))
        return PlanResult(ok=len(entries), failed=0)


def _doc(repo: str = "/r") -> dict:
    def _unsupported_cells(repo: str, slug: str, kind_dir: str) -> list[dict]:
        """Generate cells for all 4 harnesses x 2 scopes where only claude is supported."""
        cells = []
        for harness in ["claude", "codex", "opencode", "pi"]:
            for scope in ["user", "project"]:
                if harness == "claude":
                    cells.append({"harness": harness, "scope": scope, "status": "unlinked",
                                  "target": None, "allowlisted": False})
                else:
                    cells.append({"harness": harness, "scope": scope, "status": "unsupported",
                                  "target": None, "allowlisted": False})
        return cells

    return {
        "toolkit_root": repo,
        "harnesses": ["claude", "codex", "opencode", "pi"],
        "assets": [
            {
                "kind": "skill", "slug": "alpha",
                "origin": "first-party", "description": "Alpha.",
                "path": f"{repo}/skills/alpha/SKILL.md",
                "declared_harnesses": ["claude"],
                "cells": _unsupported_cells(repo, "alpha", "skills"),
            },
            {
                "kind": "agent", "slug": "my-agent",
                "origin": "first-party", "description": "My agent.",
                "path": f"{repo}/agents/my-agent/AGENT.md",
                "declared_harnesses": ["claude"],
                "cells": [
                    {"harness": "claude", "scope": "user", "status": "unlinked",
                     "target": None, "allowlisted": False},
                    {"harness": "claude", "scope": "project", "status": "unlinked",
                     "target": None, "allowlisted": False},
                    {"harness": "codex", "scope": "user", "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "codex", "scope": "project", "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "opencode", "scope": "user", "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "opencode", "scope": "project", "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "pi", "scope": "user", "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "pi", "scope": "project", "status": "unsupported",
                     "target": None, "allowlisted": False},
                ],
            },
            {
                "kind": "mcp", "slug": "demo-mcp",
                "origin": "first-party", "description": "Demo MCP.",
                "path": f"{repo}/mcps/demo-mcp/config.json",
                "declared_harnesses": ["claude"],
                # MCPs project as no-ops today (see _link_lib.project_from_file
                # and _list_json._build_inventory): every cell is "unsupported"
                # regardless of the declared harnesses.
                "cells": [
                    {"harness": h, "scope": s, "status": "unsupported",
                     "target": None, "allowlisted": False}
                    for h in ["claude", "codex", "opencode", "pi"]
                    for s in ["user", "project"]
                ],
            },
        ],
    }


async def test_space_toggles_cell_and_cursor_stays_in_place():
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        from agent_toolkit_tui.widgets import AssetGrid
        from textual.coordinate import Coordinate
        from textual.widgets import DataTable
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)
        target = Coordinate(row=0, column=1)
        table.cursor_coordinate = target
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert table.cursor_coordinate == target, (
            f"cursor jumped from {target} to {table.cursor_coordinate}"
        )
        assert grid.pending_entries(), "space should have queued a pending toggle"


async def test_second_space_clears_pending():
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        from agent_toolkit_tui.widgets import AssetGrid
        from textual.coordinate import Coordinate
        from textual.widgets import DataTable
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert grid.pending_entries(), "first space should queue a pending op"
        await pilot.press("space")
        await pilot.pause()
        assert not grid.pending_entries(), (
            "second space should un-queue the pending op (toggle-off)"
        )


async def test_app_starts_and_shows_pending_zero():
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        from textual.widgets import Static
        label = app.query_one("#footer-pending", Static)
        assert "Pending" in str(label.render())


async def test_toggle_then_apply_invokes_runner():
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Move cursor onto the (alpha, claude) cell. The grid columns are
        # [slug, claude, codex, opencode, pi]; row 0 col 1 = (alpha, claude).
        from agent_toolkit_tui.widgets import AssetGrid
        from textual.coordinate import Coordinate
        from textual.widgets import DataTable
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("enter")  # DataTable's Enter binding runs action_select_cursor
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert runner.calls, "expected at least one runner call"
        op, scope, harness, entries, dry = runner.calls[0]
        assert op == "link"
        assert scope == "user"
        assert harness == "claude"
        assert ("skill", "alpha") in entries
        assert dry is False


async def test_diff_uses_dry_run():
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        from agent_toolkit_tui.widgets import AssetGrid
        from textual.coordinate import Coordinate
        from textual.widgets import DataTable
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.press("ctrl+d")
        await pilot.pause()
        assert runner.calls, "diff should have invoked the runner"
        assert runner.calls[-1][-1] is True   # dry_run


# ---------------------------------------------------------------------------
# R-3 new pilot tests
# ---------------------------------------------------------------------------

async def test_refresh_rebuilds_state():
    """ctrl+r calls list_state again and clears pending that matches new state."""
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Toggle a cell to create a pending entry
        from agent_toolkit_tui.widgets import AssetGrid
        from textual.coordinate import Coordinate
        from textual.widgets import DataTable
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        list_calls_before = runner.list_calls
        # Refresh
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert runner.list_calls >= list_calls_before + 1, (
            "ctrl+r should trigger at least one more list_state call"
        )


async def test_scope_change_updates_grid():
    """Posting ScopeChanged updates the grid's internal scope."""
    from agent_toolkit_tui.messages import ScopeChanged
    from agent_toolkit_tui.widgets import AssetGrid

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        assert grid._scope == "user"

        # Post message directly (scope radio is not Tab-focusable)
        app.post_message(ScopeChanged(scope="project"))
        await pilot.pause()
        assert grid._scope == "project"

        # Toggle a cell and verify runner is called with scope=project
        from textual.coordinate import Coordinate
        from textual.widgets import DataTable
        table = grid.query_one("#grid-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert runner.calls, "expected at least one runner call"
        _, scope, _, _, _ = runner.calls[0]
        assert scope == "project"


async def test_kind_change_filters_grid():
    """Posting KindChanged updates the grid's kind and filters rows accordingly."""
    from agent_toolkit_tui.messages import KindChanged
    from agent_toolkit_tui.widgets import AssetGrid

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        assert grid._kind == "skill"

        # Post KindChanged for agent
        app.post_message(KindChanged(kind="agent"))
        await pilot.pause()
        assert grid._kind == "agent"

        # Only agent rows should be returned
        agent_rows = grid._rows_for_kind()
        assert all(r.kind == "agent" for r in agent_rows), (
            f"Expected only agent rows, got kinds: {[r.kind for r in agent_rows]}"
        )
        assert len(agent_rows) >= 1, "Expected at least one agent asset in fixture"


async def test_kind_change_to_mcp_filters_grid():
    """Posting KindChanged(kind='mcp') filters the grid to MCP rows. Regression for #39."""
    from agent_toolkit_tui.messages import KindChanged
    from agent_toolkit_tui.widgets import AssetGrid

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)

        app.post_message(KindChanged(kind="mcp"))
        await pilot.pause()
        assert grid._kind == "mcp"

        mcp_rows = grid._rows_for_kind()
        assert all(r.kind == "mcp" for r in mcp_rows), (
            f"Expected only mcp rows, got kinds: {[r.kind for r in mcp_rows]}"
        )
        assert len(mcp_rows) == 1, f"Expected 1 MCP row from fixture, got {len(mcp_rows)}"
        assert mcp_rows[0].slug == "demo-mcp"


async def test_harness_visibility_toggle_hides_column():
    """Unchecking a harness checkbox removes it from visible harnesses and the grid."""
    from agent_toolkit_tui.widgets import AssetGrid
    from textual.widgets import Checkbox, DataTable

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        harnesses_before = list(grid._visible_harnesses)
        assert "codex" in harnesses_before

        # Uncheck codex
        cb = app.query_one("#hcb-codex", Checkbox)
        cb.value = False
        await pilot.pause()

        assert "codex" not in grid._visible_harnesses, (
            "codex should be removed from visible harnesses"
        )
        # Grid should now have one fewer harness column (slug + remaining harnesses)
        table = grid.query_one("#grid-table", DataTable)
        expected_cols = 1 + len(grid._visible_harnesses)
        actual_cols = len(list(table.ordered_columns))
        assert actual_cols == expected_cols, (
            f"Expected {expected_cols} columns, got {actual_cols}"
        )
