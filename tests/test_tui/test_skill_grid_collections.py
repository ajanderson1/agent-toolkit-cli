from dataclasses import replace
from pathlib import Path

import pytest
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from tests.test_cli.test_skill_collection_reconcile import legacy


@pytest.mark.asyncio
async def test_hierarchy_mixed_parent_hidden_members_and_column_deduplication(legacy):
    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=(120, 40)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        assert grid.row_count == 11 and grid.collection_count == 1
        parent = grid._visible_rows()[0]
        assert parent.is_collection
        grid.cursor_to_cell(row_slug="workflow-00", agent_name="standard")
        await pilot.press("space")
        assert "−" in grid._cell_glyph(row=parent, agent="standard")
        assert "-" in grid._cell_glyph(row=grid._rows[0], agent="standard")
        grid.set_filter("workflow-00")
        assert len(grid._visible_rows()) == 2
        grid._toggle_at(Coordinate(0, 1))
        assert grid.pending_entries() == {}  # mixed -> all cancels the child removal
        grid._toggle_at(Coordinate(0, 1))
        assert len(grid.pending_entries()) == 11
        assert all(not k[2].startswith("collection:") for k in grid.pending_entries())
        grid._toggle_at(Coordinate(0, 1))
        assert not grid.pending_entries()
        grid.set_filter("")
        grid._toggle_at(Coordinate(0, 0))
        assert len(grid._visible_rows()) == 1
        grid._toggle_at(Coordinate(0, 1))
        assert len(grid.pending_entries()) == 11
        table = grid.query_one("#skill-table", DataTable)
        table.cursor_coordinate = Coordinate(0, 1)
        grid.action_toggle_column()
        assert not grid.pending_entries()
        assert (Path.home() / ".agents/skills/wrapper").exists()


@pytest.mark.asyncio
async def test_left_from_nonleftmost_column_keeps_table_navigation(legacy):
    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=(180, 50)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        table = grid.query_one("#skill-table", DataTable)

        table.focus()
        table.cursor_coordinate = Coordinate(0, 0)
        await pilot.press("right", "right", "left")
        await pilot.pause()

        assert table.cursor_coordinate == Coordinate(0, 0)
        assert len(grid._visible_rows()) == 12


@pytest.mark.asyncio
async def test_left_in_leftmost_column_collapses_collection_or_selected_child_parent(legacy):
    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=(180, 50)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        table = grid.query_one("#skill-table", DataTable)

        parent_slug = grid._visible_rows()[0].slug
        table.focus()
        table.cursor_coordinate = Coordinate(0, 0)
        await pilot.press("left")
        await pilot.pause()
        assert len(grid._visible_rows()) == 1

        grid._collapsed.clear()
        second_key = ("other/repo", None)
        second_child = replace(
            grid._rows[0],
            slug="z-second-child",
            collection_key=second_key,
            collection_label="other/repo",
            display_name="second-child",
        )
        standalone = replace(
            grid._rows[0],
            slug="z-standalone",
            collection_key=None,
            collection_label="",
            display_name="z-standalone",
        )
        grid.set_rows([*grid._rows, second_child, standalone])
        grid.cursor_to_cell(row_slug="z-second-child", agent_name="standard")
        table.focus()
        table.cursor_coordinate = Coordinate(1, 0)
        await pilot.press("left")
        await pilot.pause()

        assert [row.slug for row in grid._visible_rows()] == [
            parent_slug,
            f"collection:{second_key!r}",
            "z-second-child",
            "z-standalone",
        ]
        assert table.cursor_coordinate == Coordinate(0, 0)
        assert app.focused is table


@pytest.mark.asyncio
async def test_unavailable_parent_does_not_queue(legacy):
    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=(180, 50)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        parent = grid._visible_rows()[0]
        assert "—" in grid._cell_glyph(row=parent, agent="paperclip")
        grid._toggle_at(Coordinate(0, grid._column_index("paperclip")))
        assert not grid.pending_entries()


@pytest.mark.asyncio
async def test_right_expands_collapsed_parent_before_moving_to_harness_column(legacy):
    app = TUIApp()
    async with app.run_test(size=(180, 50)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        table = grid.query_one("#skill-table", DataTable)
        grid._collapsed.add(grid._visible_rows()[0].collection_key)
        grid.set_filter("")
        assert len(grid._visible_rows()) == 1
        table.focus()
        table.cursor_coordinate = Coordinate(0, 0)

        await pilot.press("right")
        assert len(grid._visible_rows()) == 12
        assert table.cursor_coordinate == Coordinate(0, 0)
        await pilot.press("right")
        assert table.cursor_coordinate == Coordinate(0, 1)
        await pilot.press("right")
        assert table.cursor_coordinate == Coordinate(0, 2)
        assert not grid.pending_entries()


@pytest.mark.asyncio
async def test_right_on_filter_revealed_parent_moves_without_changing_collapse_choice(legacy):
    app = TUIApp()
    async with app.run_test(size=(180, 50)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        table = grid.query_one("#skill-table", DataTable)
        key = grid._visible_rows()[0].collection_key
        grid._collapsed.add(key)
        grid.set_filter("workflow-00")
        assert len(grid._visible_rows()) == 2
        table.focus()
        table.cursor_coordinate = Coordinate(0, 0)

        await pilot.press("right")
        assert table.cursor_coordinate == Coordinate(0, 1)
        assert key in grid._collapsed
        assert not grid.pending_entries()
