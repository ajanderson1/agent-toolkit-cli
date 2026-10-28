"""Keep unchanged table rows intact without hiding any cell-state changes."""
from __future__ import annotations

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.skill_state import SkillCell, SkillRow, interactive_agents
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


class GridApp(App):
    def compose(self) -> ComposeResult:
        cells = {(h, "global"): SkillCell(False, False, False) for h in interactive_agents()}
        yield SkillGrid([
            SkillRow(slug="alpha", source="example/repo", ref="main", state="clean", cells=cells),
            SkillRow(slug="beta", source="example/repo", ref="main", state="dirty", cells=cells),
        ])


@pytest.mark.asyncio
async def test_toggle_updates_state_without_recreating_rows():
    app = GridApp()
    async with app.run_test() as pilot:
        grid = app.query_one(SkillGrid)
        table = app.query_one(DataTable)
        await pilot.pause()
        table.cursor_coordinate = Coordinate(0, 1)
        old_rows = dict(table.rows)
        old_columns = dict(table.columns)
        before = list(table.get_row_at(0))
        grid.action_toggle_cell()
        await pilot.pause()
        after = table.get_row_at(0)
        assert grid.pending_entries() == {("global", "standard", "alpha"): "link"}
        assert after[1] != before[1]
        assert after[0] == before[0]
        assert after[-2:] == before[-2:]
        assert all(table.rows[key] is row for key, row in old_rows.items())
        assert all(table.columns[key] is col for key, col in old_columns.items())


def test_collection_members_do_not_rescan_inventory_and_refresh_with_rows():
    class CountedRows(list):
        iterations = 0

        def __iter__(self):
            self.iterations += 1
            return super().__iter__()

    key = ("example/repo", "main")
    first = SkillRow("alpha", "example/repo", "main", "clean", collection_key=key)
    second = SkillRow("beta", "example/repo", "main", "dirty", collection_key=key)
    grid = SkillGrid([first, second])
    parent = SkillRow("parent", "example/repo", "main", "clean", collection_key=key, is_collection=True)
    counted = CountedRows(grid._rows)
    grid._rows = counted
    assert grid._members(parent) == [first, second]
    assert grid._members(parent) == [first, second]
    assert counted.iterations == 0
    grid.set_rows([second])
    assert grid._members(parent) == [second]
    assert grid.collection_count == 1
    grid.set_rows([])
    assert grid._members(parent) == []
    assert grid.collection_count == 0
    second.collection_key = None
    grid.set_rows([second])
    second.collection_key = key
    grid._visible_rows()
    assert grid._members(parent) == [second]
    assert grid.collection_count == 1


@pytest.mark.parametrize("kind", ["skill", "agent", "command", "instruction", "mcp", "pi"])
@pytest.mark.asyncio
async def test_all_grids_reuse_rows_and_refresh_source_and_pending(kind):
    from agent_toolkit_tui.agent_state import AgentCell, AgentRow
    from agent_toolkit_tui.command_state import CommandCell, CommandRow
    from agent_toolkit_tui.instruction_state import InstructionCell, InstructionRow
    from agent_toolkit_tui.mcp_state import McpCell, McpRow
    from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
    from agent_toolkit_tui.widgets import AgentGrid, CommandGrid, InstructionGrid, McpGrid, PiGrid

    cells = {("standard", "global"): SkillCell(False, False, False)}
    definitions = {
        "skill": (SkillGrid, SkillRow("demo", "old", "main", "clean", cells)),
        "agent": (AgentGrid, AgentRow("demo", "old", "main", cells={("standard", "global"): AgentCell(False)})),
        "command": (CommandGrid, CommandRow("demo", "old", "main", cells={("standard", "global"): CommandCell(False)})),
        "instruction": (InstructionGrid, InstructionRow("demo", "old", True, {("claude-code", "global"): InstructionCell(False, False)})),
        "mcp": (McpGrid, McpRow("demo", "old", cells={("claude-code", "global"): McpCell(False)})),
        "pi": (PiGrid, PiExtensionRow("demo", "git", "old", PiCell(False, False, "git"), PiCell(False, False, "git"))),
    }
    grid_type, row = definitions[kind]
    grid = grid_type([row])

    class OneGridApp(App):
        def compose(self) -> ComposeResult:
            yield grid

    async with OneGridApp().run_test() as pilot:
        await pilot.pause()
        table = grid.query_one(DataTable)
        original_row = next(iter(table.rows.values()))
        before = table.get_row_at(0)
        harness = "claude-code" if kind in ("instruction", "mcp") else "standard"
        key = ("global", "demo") if kind == "pi" else ("global", harness, "demo")
        row.source = "new-source"
        grid.restore_pending({key: "link"})
        await pilot.pause()
        assert next(iter(table.rows.values())) is original_row
        assert "new-source" in str(table.get_row_at(0)[-1])
        assert table.get_row_at(0) != before
        assert grid.pending_entries() == {key: "link"}
        grid.clear_pending()
        assert grid.pending_entries() == {}
        assert next(iter(table.rows.values())) is original_row


@pytest.mark.asyncio
async def test_sync_updates_all_state_and_handles_structure_changes():
    from agent_toolkit_tui.widgets._support import sync_table

    class TableApp(App):
        def compose(self) -> ComposeResult:
            yield DataTable()

    app = TableApp()
    async with app.run_test() as pilot:
        table = app.query_one(DataTable)
        columns = [("Asset", 20), ("State", 12), ("Source", 30)]
        sync_table(table, columns, [("a", ["alpha", "clean", Text("old")])])
        await pilot.pause()
        original = table.rows[next(iter(table.rows))]
        sync_table(table, columns, [("a", ["alpha", "[red]missing[/]", Text("new", style="bold")])])
        assert table.get_row("a") == ["alpha", "[red]missing[/]", Text("new", style="bold")]
        assert table.rows[next(iter(table.rows))] is original
        sync_table(table, columns, [("b", ["beta", "dirty", "local"])])
        assert table.get_row_at(0) == ["beta", "dirty", "local"]
        sync_table(table, [("Changed", 25)], [("b", ["beta"])])
        assert table.ordered_columns[0].label.plain == "Changed"
        assert table.ordered_columns[0].width == 25
        sync_table(table, [("Changed", 25)], [])
        assert table.row_count == 0
