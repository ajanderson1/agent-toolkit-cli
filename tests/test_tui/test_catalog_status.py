"""Persistent catalogue state and collection keyboard behaviour in the real TUI."""

import os
from pathlib import Path

import pytest
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Static

from agent_toolkit_cli.skill_catalog import CatalogSnapshot
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.screens.cell_info import CellInfoScreen
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from tests.test_cli.test_reground import sandbox, git, invoke
from tests.test_cli.test_skill_catalog import catalog_repo
from tests.test_cli.test_skill_collection_reconcile import legacy


@pytest.mark.asyncio
async def test_unsubscribed_invalid_and_stale_refresh_states(sandbox):
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        badge = app.query_one("#catalog-status", Static)
        assert str(badge.render()) == "Catalogue: not subscribed"
        old_generation = app._skill_catalog_generation
        config = sandbox / ".agent-toolkit/config.json"
        config.parent.mkdir(exist_ok=True)
        config.write_text("{")
        app._start_catalog_refresh()
        assert str(badge.render()) == "Catalogue: unavailable"
        config.unlink()
        app._start_catalog_refresh()
        assert str(badge.render()) == "Catalogue: not subscribed"
        stale = CatalogSnapshot("old", revision="old-revision", version="v9.9.9")
        app._finish_skill_catalog(old_generation, app._scope, sandbox, None, stale)
        assert str(badge.render()) == "Catalogue: not subscribed"
        app._finish_skill_catalog(app._skill_catalog_generation, "global", sandbox, None, stale)
        assert str(badge.render()) == "Catalogue: not subscribed"


@pytest.mark.asyncio
async def test_catalogue_status_updates_even_while_info_modal_is_open(sandbox):
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        badge = app.query_one("#catalog-status", Static)
        app.push_screen(CellInfoScreen(title="Fixture", body_markup="Fixture"))
        await pilot.pause()
        snapshot = CatalogSnapshot("fixture", revision="fetched-revision", version="v1.2.3")
        app._finish_skill_catalog(app._skill_catalog_generation, app._scope, sandbox, None, snapshot)
        app.pop_screen()
        await pilot.pause()
        assert str(badge.render()) == "Catalogue: v1.2.3"


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_collapsed_then_right_twice_with_persistent_release_status(legacy, tmp_path, size):
    root = tmp_path / "catalogue-fixture"
    root.mkdir()
    cat = catalog_repo(root, {"version": 2, "entries": []})
    git(cat, "tag", "v1.1.0")
    invoke("catalog", "subscribe", cat.as_uri())
    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=size) as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        grid = app.query_one(SkillGrid)
        table = grid.query_one(DataTable)
        badge = app.query_one("#catalog-status", Static)
        assert str(badge.render()) == "Catalogue: v1.1.0"
        assert len(grid._visible_rows()) == 1
        output = os.environ.get("ATK_NAV_CAPTURE_DIR")
        if output:
            Path(output).mkdir(parents=True, exist_ok=True)
            app.save_screenshot(path=output, filename=f"{size[0]}-collapsed.svg")
        table.focus()
        table.cursor_coordinate = Coordinate(0, 0)
        await pilot.press("right")
        assert len(grid._visible_rows()) == 12
        assert table.cursor_coordinate == Coordinate(0, 0)
        await pilot.press("right")
        assert table.cursor_coordinate == Coordinate(0, 1)
        assert not grid.pending_entries()
        assert badge.region.height == 1
        assert badge.region.right == size[0]
        assert str(badge.render()) == "Catalogue: v1.1.0"
        if output:
            app.save_screenshot(path=output, filename=f"{size[0]}-expanded-second-column.svg")
