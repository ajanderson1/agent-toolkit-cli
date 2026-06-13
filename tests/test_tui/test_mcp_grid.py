import pytest

from agent_toolkit_tui.mcp_state import McpRow
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
