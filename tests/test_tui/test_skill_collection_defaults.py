"""Collection defaults and refreshes preserve explicit navigation choices."""

import pytest
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.skill_state import SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from tests.test_cli.test_skill_collection_reconcile import legacy


def child(name, source="owner/repo"):
    return SkillRow(name, source, "main", "clean", collection_key=(source, "main"),
                    collection_label=source, display_name=name)


def test_initial_collections_are_collapsed_but_standalone_skills_remain_visible():
    standalone = SkillRow("z-standalone", "owner/solo", "main", "clean")
    grid = SkillGrid([child("a"), child("b"), standalone])
    visible = grid._visible_rows()
    assert len(visible) == 2
    assert visible[0].is_collection
    assert visible[1] is standalone
    assert grid.row_count == 3


def test_refresh_collapses_new_collections_without_resetting_existing_choices():
    first = child("a")
    second = child("z", "other/repo")
    grid = SkillGrid([first])
    grid._collapsed.discard(first.collection_key)  # User expanded the first group.
    grid.set_rows([first, second])
    assert [r.slug for r in grid._visible_rows() if not r.is_collection] == ["a"]
    grid.set_rows([first, second])
    assert first.collection_key not in grid._collapsed
    assert second.collection_key in grid._collapsed
    grid.set_rows([first])
    assert second.collection_key not in grid._collapsed
    grid.set_rows([first, second])
    assert second.collection_key in grid._collapsed


@pytest.mark.asyncio
async def test_navigation_to_hidden_child_expands_its_collection_without_queuing(legacy):
    app = TUIApp()
    async with app.run_test(size=(180, 50)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        assert len(grid._visible_rows()) == 1
        grid.cursor_to_cell(row_slug="workflow-07", agent_name="standard")
        await pilot.pause()
        table = grid.query_one("#skill-table", DataTable)
        assert len(grid._visible_rows()) == 12
        assert table.cursor_coordinate == Coordinate(8, 1)
        assert app.focused is table
        assert not grid.pending_entries()
