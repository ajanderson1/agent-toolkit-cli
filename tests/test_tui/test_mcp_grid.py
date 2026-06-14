import pytest

from agent_toolkit_tui.mcp_state import McpCell, McpRow
from agent_toolkit_tui.widgets.mcp_grid import McpGrid


def _row(slug="ctx7", **cells):
    return McpRow(slug=slug, source="npx", pin=None, state="installed",
                  cells=dict(cells))


@pytest.mark.asyncio
async def test_columns_project_have_standard(monkeypatch):
    from textual.app import App

    class _A(App):
        def compose(self):
            yield McpGrid([_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        grid = app.query_one("#g", McpGrid)
        grid.set_scope("project")
        grid.set_rows([_row()])
        await pilot.pause()
        from textual.widgets import DataTable
        labels = [str(c.label) for c in
                  app.query_one(DataTable).columns.values()]
        assert any("Standard" in s for s in labels)
        assert any("codex" in s for s in labels)
        assert not any("claude-code" in s for s in labels)  # folded into standard


@pytest.mark.asyncio
async def test_columns_global_no_standard(monkeypatch):
    from textual.app import App

    class _A(App):
        def compose(self):
            yield McpGrid([_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        grid = app.query_one("#g", McpGrid)
        grid.set_scope("global")
        grid.set_rows([_row()])
        await pilot.pause()
        from textual.widgets import DataTable
        labels = [str(c.label) for c in
                  app.query_one(DataTable).columns.values()]
        assert not any("Standard" in s for s in labels)
        assert any("claude-code" in s for s in labels)
        assert any("pi" in s for s in labels)


@pytest.mark.asyncio
async def test_standard_cell_toggles_pending():
    from textual.app import App
    from textual.coordinate import Coordinate

    class _A(App):
        def compose(self):
            yield McpGrid([_row()], id="g")

    # Seed the standard cell so it is toggleable: a row with no
    # ("standard", "project") cell is "not applicable at this scope" and the
    # toggle correctly no-ops (same contract as agent_grid). The standard
    # cell IS a real installable destination at project scope, so seed it.
    seeded = McpRow(slug="ctx7", source="npx", pin=None, state="installed",
                    cells={("standard", "project"): McpCell(linked=False)})

    app = _A()
    async with app.run_test() as pilot:
        grid = app.query_one("#g", McpGrid)
        grid.set_scope("project")
        grid.set_rows([seeded])
        await pilot.pause()
        from textual.widgets import DataTable
        table = app.query_one(DataTable)
        table.cursor_coordinate = Coordinate(0, 1)  # col 1 == standard
        grid.action_toggle_cell()
        await pilot.pause()
        pend = grid.pending_entries()
        assert ("project", "standard", "ctx7") in pend


def test_context_for_standard_is_mcps():
    grid = McpGrid([_row()])
    grid.set_scope("project")
    grid.set_rows([_row()])
    ctx = grid._context_for(key="standard", row_index=0)
    assert ctx is not None
    assert ctx["asset_type"] == "mcps"
    assert set(ctx["names"]) == {"claude-code", "pi"}
    assert ctx["global_linked"] is False
    # F9: the modal spells out the fold (one cell = N harnesses, project-only).
    joined = "\n".join(ctx["extra_lines"])
    assert "installs into all 2" in joined
    assert "Project scope only" in joined


def test_column_info_mcps_title_not_bundle():
    # F5: the Standard column-info title for mcps must NOT be "Standard bundle".
    from agent_toolkit_tui.column_info import get_column_info
    info = get_column_info("standard", context={
        "asset_type": "mcps", "names": ("claude-code", "pi"),
        "extra_lines": [], "global_linked": False,
    })
    assert info is not None
    assert info.title == "Standard projection (.mcp.json)"
    assert "bundle" not in info.title.lower()


@pytest.mark.asyncio
async def test_app_shows_mcp_grid_on_select():
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.mcp_grid import McpGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("mcp")
        await pilot.pause()
        grid = app.query_one("#mcp-grid", McpGrid)
        assert grid.display is True
        # The other grids are hidden.
        from agent_toolkit_tui.widgets import AgentGrid
        assert app.query_one("#agent-grid", AgentGrid).display is False


@pytest.mark.asyncio
async def test_scope_toggle_rebuilds_mcp_columns():
    from textual.widgets import DataTable
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("mcp")
        await pilot.pause()
        # Default scope (project): Standard column present.
        def labels():
            return [str(c.label) for c in
                    app.query_one("#mcp-grid DataTable", DataTable).columns.values()]
        if app._scope != "project":
            app.action_scope_toggle()
            await pilot.pause()
        assert any("Standard" in s for s in labels())
        app.action_scope_toggle()  # → global
        await pilot.pause()
        assert not any("Standard" in s for s in labels())
        assert any("claude-code" in s for s in labels())


@pytest.mark.asyncio
async def test_mcp_tab_header_and_pending_label_parity():
    # Parity with the agent tab (AC4): while MCP is active, the content header
    # counts the MCP grid's rows (not the agent grid's), and the footer pending
    # label includes MCP pending entries. Both are app-level rollups that must
    # treat #mcp-grid like every other grid.
    from agent_toolkit_tui.app import TUIApp
    from textual.widgets import Static

    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("mcp")
        await pilot.pause()
        grid = app.query_one("#mcp-grid", McpGrid)
        grid.set_scope("project")
        grid.set_rows([_row("a"), _row("b")])
        # The header refreshes on switch/scope-toggle (same as every grid), so
        # trigger a refresh after seeding rows.
        app._refresh_content_header()
        await pilot.pause()
        # Header reflects the MCP grid's row count (2), labelled MCP.
        header = str(app.query_one("#content-header", Static).render())
        assert "MCP" in header
        assert "2 items" in header
        # Pending label counts MCP pending entries.
        grid.restore_pending({("project", "codex", "a"): "link"})
        app._refresh_pending_label()
        await pilot.pause()
        footer = str(app.query_one("#footer-pending", Static).render())
        assert "Pending: 1" in footer
