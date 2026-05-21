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
        """Generate cells for all 5 harnesses x 2 scopes where only claude is supported."""
        cells = []
        for harness in ["claude", "codex", "opencode", "gemini", "pi"]:
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
        "harnesses": ["claude", "codex", "opencode", "gemini", "pi"],
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
                    {"harness": "gemini", "scope": "user", "status": "unsupported",
                     "target": None, "allowlisted": False},
                    {"harness": "gemini", "scope": "project", "status": "unsupported",
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
                # regardless of declared harnesses.
                "cells": [
                    {"harness": h, "scope": s, "status": "unsupported",
                     "target": None, "allowlisted": False}
                    for h in ["claude", "codex", "opencode", "gemini", "pi"]
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


def _long_doc(row_count: int = 50, repo: str = "/r") -> dict:
    """Build a doc with *row_count* skills so the DataTable overflows a 24-row terminal."""
    assets = []
    for i in range(row_count):
        slug = f"skill-{i:03d}"
        assets.append({
            "kind": "skill", "slug": slug,
            "origin": "first-party", "description": f"Skill {i}.",
            "path": f"{repo}/skills/{slug}/SKILL.md",
            "declared_harnesses": ["claude"],
            "cells": [
                {"harness": "claude", "scope": "user", "status": "unlinked",
                 "target": None, "allowlisted": False},
                {"harness": "claude", "scope": "project", "status": "unlinked",
                 "target": None, "allowlisted": False},
            ],
        })
    return {
        "toolkit_root": repo,
        "harnesses": ["claude"],
        "assets": assets,
    }


async def test_toggle_preserves_scroll_position_and_cursor():
    runner = FakeRunner(_long_doc(50))
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        from agent_toolkit_tui.widgets import AssetGrid
        from textual.coordinate import Coordinate
        from textual.widgets import DataTable
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)
        table.focus()
        await pilot.pause()
        # Place cursor on a harness column partway down, then scroll past it so
        # the cursor sits near the top of the viewport (scroll_y > 0 and the
        # cursor would NOT be at the minimal scroll-into-view position).
        # This exposes the bug: _rebuild clears → scroll resets → cursor restore
        # scrolls back to the cursor's minimal position, not the user's position.
        table.cursor_coordinate = Coordinate(row=20, column=1)
        await pilot.pause()
        # Scroll so cursor row 20 appears near the top (scroll_y=10 means rows
        # 10-16 are visible, but cursor is at row 20 which is NOT visible →
        # Textual will scroll-to-cursor on the next interaction, so instead
        # scroll so cursor IS visible but not at the viewport minimum).
        # Use scroll_to to set a specific offset: put row 18 at the top so
        # cursor (row 20) is 2 rows from top — well within viewport.
        table.scroll_to(0, 18, animate=False)
        await pilot.pause()
        before_scroll = table.scroll_y
        assert before_scroll > 0, (
            f"fixture did not scroll (scroll_y={before_scroll}); "
            "check scroll_to call"
        )
        before_cursor = table.cursor_coordinate
        await pilot.press("space")
        await pilot.pause()
        assert table.scroll_y == before_scroll, (
            f"scroll_y changed after toggle: {before_scroll} -> {table.scroll_y}"
        )
        assert table.cursor_coordinate == before_cursor, (
            f"cursor jumped after toggle: {before_cursor} -> {table.cursor_coordinate}"
        )


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
        assert scope == "project"
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
        assert grid._scope == "project"

        # Post message directly (scope radio is not Tab-focusable)
        app.post_message(ScopeChanged(scope="user"))
        await pilot.pause()
        assert grid._scope == "user"

        # Toggle a cell and verify runner is called with scope=user
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
        assert scope == "user"


async def test_a_key_links_all_in_column_then_unlinks_all():
    """Pressing 'a' on a column links all visible+supported rows; pressing again unlinks all."""
    from agent_toolkit_tui.widgets import AssetGrid
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    # Build a doc with two skills, both unlinked on claude.
    doc = _doc()
    doc["assets"].append({
        "kind": "skill", "slug": "beta",
        "origin": "first-party", "description": "Beta.",
        "path": "/r/skills/beta/SKILL.md",
        "declared_harnesses": ["claude"],
        "cells": [
            {"harness": "claude", "scope": "user", "status": "unlinked",
             "target": None, "allowlisted": False},
            {"harness": "claude", "scope": "project", "status": "unlinked",
             "target": None, "allowlisted": False},
            *[{"harness": h, "scope": s, "status": "unsupported",
               "target": None, "allowlisted": False}
              for h in ("codex", "opencode", "gemini", "pi") for s in ("user", "project")],
        ],
    })
    runner = FakeRunner(doc)
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)
        # Cursor on row 0, claude column (col 1).
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        pending = grid.pending_entries()
        # Both skills should be queued for link on (project, claude).
        assert ("project", "claude", "skill", "alpha") in pending
        assert ("project", "claude", "skill", "beta") in pending
        assert all(op == "link" for op in pending.values())

        # Pressing 'a' again with all-pending-link should clear them
        # (unlink would no-op since ground truth is unlinked).
        await pilot.press("a")
        await pilot.pause()
        assert grid.pending_entries() == {}, (
            f"second 'a' should clear pending, got {grid.pending_entries()}"
        )


async def test_a_key_skips_unsupported_cells():
    """'a' on an unsupported column queues nothing."""
    from agent_toolkit_tui.widgets import AssetGrid
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)
        # codex column (col 2) — unsupported for the skill row.
        table.cursor_coordinate = Coordinate(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert grid.pending_entries() == {}, (
            "'a' on unsupported column should not queue anything"
        )


async def test_ctrl_z_reverts_all_pending():
    """Ctrl+Z clears the pending queue without applying anything."""
    from agent_toolkit_tui.widgets import AssetGrid
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)
        # Queue a link on the alpha/claude/project cell.
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert grid.pending_entries(), "precondition: should have a pending entry"

        await pilot.press("ctrl+z")
        await pilot.pause()
        assert grid.pending_entries() == {}, "ctrl+z should clear pending"
        # Revert must NOT call the runner.
        assert runner.calls == [], (
            f"revert must not invoke runner, got {runner.calls}"
        )


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


async def test_quit_with_no_pending_exits_immediately():
    """No pending edits -> q quits without prompting."""
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
    # If we got here without hanging, the modal was not shown.
    assert app.return_code is not None or app._exit, "app should have exited"


async def test_quit_with_pending_prompts_and_cancel_keeps_state():
    """With pending edits, q opens the discard modal; pressing 'n' cancels."""
    from agent_toolkit_tui.app import ConfirmDiscardScreen
    from agent_toolkit_tui.widgets import AssetGrid
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert grid.pending_entries(), "precondition: pending edit"

        await pilot.press("q")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDiscardScreen), (
            f"expected ConfirmDiscardScreen, got {type(app.screen).__name__}"
        )

        # Cancel — pending edits preserved, app keeps running.
        await pilot.press("n")
        await pilot.pause()
        assert not isinstance(app.screen, ConfirmDiscardScreen), "modal should dismiss"
        assert grid.pending_entries(), "cancel must not clear pending"


async def test_quit_with_pending_and_confirm_discards_and_exits():
    """With pending edits, q -> y discards and quits."""
    from agent_toolkit_tui.widgets import AssetGrid
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert grid.pending_entries(), "precondition: pending edit"

        await pilot.press("q")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    # Discarding does not call the runner — pending is dropped, app exits.
    assert runner.calls == [], f"discard must not invoke runner, got {runner.calls}"


async def test_space_on_unsupported_cell_is_noop():
    """Pressing Space on an `unsupported` cell yields no AssetToggled and
    no pending entry. Regression for issue #30."""
    from agent_toolkit_tui.messages import KindChanged
    from agent_toolkit_tui.widgets import AssetGrid
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    # _doc() already contains "my-agent" (kind=agent) whose codex/opencode/pi
    # cells are all "unsupported". Switch the grid to kind=agent so that row
    # is visible, then press Space on codex (column 2).
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        table = grid.query_one("#grid-table", DataTable)

        # Switch to agent kind so "my-agent" is rendered.
        app.post_message(KindChanged(kind="agent"))
        await pilot.pause()

        # Columns: 0=slug, 1=claude, 2=codex (unsupported), 3=opencode, 4=pi.
        # Row 0 is the only agent row ("my-agent").
        table.cursor_coordinate = Coordinate(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

        assert not grid.pending_entries(), (
            "Space on an unsupported cell must not queue a pending edit"
        )



# ── Dashboard layout: new keybindings (#43) ───────────────────────────────

async def test_number_key_switches_kind():
    """Pressing 1-7 changes the active kind in AssetGrid and KindsSidebar."""
    from agent_toolkit_tui.widgets import AssetGrid, KindsSidebar

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        sidebar = app.query_one("#kinds-sidebar", KindsSidebar)
        assert grid._kind == "skill"
        assert sidebar._active == "skill"

        await pilot.press("2")  # agents
        await pilot.pause()
        assert grid._kind == "agent"
        assert sidebar._active == "agent"

        await pilot.press("3")  # commands
        await pilot.pause()
        assert grid._kind == "command"
        assert sidebar._active == "command"

        await pilot.press("6")  # mcps  (#39)
        await pilot.pause()
        assert grid._kind == "mcp"
        assert sidebar._active == "mcp"

        await pilot.press("7")  # pi-extension (shifted from 6 → 7 by #39)
        await pilot.pause()
        assert grid._kind == "pi-extension"
        assert sidebar._active == "pi-extension"


async def test_s_key_toggles_scope():
    """Pressing s toggles between project and user scopes."""
    from agent_toolkit_tui.widgets import AssetGrid

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        assert grid._scope == "project"

        await pilot.press("s")
        await pilot.pause()
        assert grid._scope == "user"

        await pilot.press("s")
        await pilot.pause()
        assert grid._scope == "project"


async def test_breadcrumb_reflects_current_kind_and_scope():
    """The content header shows the kind; scope lives in the ScopeToggle sibling."""
    from textual.widgets import Static

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.query_one("#content-header", Static)
        text = str(header.render())
        assert "Skill" in text
        assert app._scope == "project"
        # Regression: V1 Navigator must NOT show global "harnesses:" chips.
        assert "harnesses" not in text.lower()

        await pilot.press("2")  # agent
        await pilot.press("s")  # toggle scope → user
        await pilot.pause()
        text = str(app.query_one("#content-header", Static).render())
        assert "Agent" in text
        assert app._scope == "user"
        assert "harnesses" not in text.lower()


async def test_content_header_renders_with_nonzero_height():
    """Regression for #52: the content-header must occupy >= 1 row on screen.

    The string built by `_build_content_header` already passes a Static.render()
    test, but a CSS bug (height: 2 - padding-bottom 1 - border-bottom 1 = 0)
    silently clipped the content area to zero rows. This test fires the moment
    the box collapses again.
    """
    from textual.widgets import Static

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        header = app.query_one("#content-header", Static)
        # `size.height` is the region Textual actually allocated for the widget
        # after CSS resolved. A zero-height region is the bug.
        assert header.size.height >= 1, (
            f"#content-header collapsed to height={header.size.height}; "
            f"chips and kind label would be invisible on screen."
        )


async def test_scope_toggle_click_switches_scope():
    """Regression for #99: clicking the inactive scope label flips _scope.

    Previously the chips were Rich-markup spans with [@click=...] action
    links; in practice these did not receive mouse clicks reliably. Now
    each scope is a Label widget inside ScopeToggle with an explicit
    on_click handler — verified here by pilot.click on the label id.
    """
    from agent_toolkit_tui.widgets import AssetGrid

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        grid = app.query_one("#asset-grid", AssetGrid)
        assert app._scope == "project"
        assert grid._scope == "project"

        # Mouse-click the inactive (user) label. This exercises the real
        # hit-test path, not just the action dispatch.
        await pilot.click("#scope-toggle-user")
        await pilot.pause()
        assert app._scope == "user"
        assert grid._scope == "user"

        # Click the (now-inactive) project label to flip back.
        await pilot.click("#scope-toggle-project")
        await pilot.pause()
        assert app._scope == "project"
        assert grid._scope == "project"


async def test_scope_keyboard_toggle_still_works():
    """Regression for #99: the 's' keybinding still toggles scope after the
    chips were replaced by the ScopeToggle widget. Keyboard path is unchanged.
    """
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        assert app._scope == "project"
        await pilot.press("s")
        await pilot.pause()
        assert app._scope == "user"
        await pilot.press("s")
        await pilot.pause()
        assert app._scope == "project"


async def test_content_header_markup_is_kind_and_count_only():
    """Regression for #99: scope chips moved out of the Static markup into a
    sibling ScopeToggle widget. The content-header markup is now just the
    kind label + item count — no Rich [@click=...] action links.
    """
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        markup = app._build_content_header()
        assert "@click" not in markup, markup
        assert markup.count("[dim]") == 1, markup  # the · separator only
        # The kind label and count must still be present.
        assert "items" in markup


async def test_status_bar_shows_summary_counts():
    """The status bar reports linked / pending / drifted / broken roll-up."""
    from textual.widgets import Static

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        text = str(app.query_one("#status-bar", Static).render())
        assert "linked" in text
        assert "pending" in text
        assert "drifted" in text
        assert "broken" in text


# ── V1 Navigator: theme + version + no harness chips ──────────────────────

async def test_default_theme_is_gruvbox():
    """on_mount sets self.theme = 'gruvbox' (matches claude_tui_tools)."""
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "gruvbox"


async def test_subtitle_shows_version():
    """Header subtitle exposes the package version, e.g. 'v0.3.0' or 'vunknown'."""
    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        sub = app.sub_title
        # Either "v<X.Y.Z>" if installed, or "vunknown" in a non-installed dev shell.
        assert sub.startswith("v"), f"sub_title should start with 'v', got {sub!r}"
        assert len(sub) >= 2, "sub_title should include some version text"


async def test_skill_tab_renders_lock_rows(git_sandbox, tmp_path, monkeypatch):
    """When the skill kind is active, SkillGrid mounts and reads the lock file."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main as cli_main
    from agent_toolkit_tui.widgets.skill_grid import SkillGrid

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    CliRunner().invoke(cli_main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    # Default kind is "skill"; explicitly toggle TUI scope to "user" so the
    # skill data path resolves to global (HOME) lock.
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_scope("user")
        await pilot.pause()
        grid = app.query_one(SkillGrid)
        assert grid.row_slugs == ["demo"]


async def test_no_harness_chips_anywhere_outside_grid():
    """Regression for #43 reopen — no global 'harnesses: claude codex …' chip row."""
    from textual.widgets import Static

    runner = FakeRunner(_doc())
    app = TUIApp(toolkit_root=Path("/r"), runner=runner)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Walk every Static and assert none of them render a "harnesses:" chip line.
        for static in app.query(Static):
            text = str(static.render()).lower()
            assert "harnesses:" not in text, (
                f"unexpected 'harnesses:' chip line in #{static.id}: {text!r}"
            )
