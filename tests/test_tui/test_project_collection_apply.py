import pytest

from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import library_lock_path, lock_file_path
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from tests.test_cli.test_project_collection_regression import (
    NAMES, SELECTED, assert_inventory, findings, project_collection, rows,
    seed_post_doctor, snapshot, convert,
)
from agent_toolkit_cli.skill_collections import projection


@pytest.mark.asyncio
async def test_project_apply_refresh_and_new_app(project_collection, tmp_path):
    home, project, backings, _ = project_collection
    before = [snapshot(b) for b in backings]
    library = library_lock_path().read_bytes()
    app = TUIApp(cwd=project)
    app._scope = "project"
    async with app.run_test(size=(180, 50)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        assert grid.row_count == 11
        for name in sorted(NAMES - SELECTED):
            grid.cursor_to_cell(row_slug=name, agent_name="standard")
            await pilot.press("space")
        app.action_apply()
        await pilot.pause()
        assert not grid.pending_entries()
        app.save_screenshot(str(tmp_path / "after-project-apply.svg"))
        assert_inventory(rows(project_collection))
        app.action_refresh()
        await pilot.pause()
        assert grid.row_count == 11
        assert_inventory(rows(project_collection))
    assert library_lock_path().read_bytes() == library
    assert set(read_lock(lock_file_path(scope="project", project=project)).skills) == NAMES
    assert [snapshot(b) for b in backings] == before
    seed_post_doctor(project_collection)
    fresh = TUIApp(cwd=project)
    fresh._scope = "project"
    async with fresh.run_test(size=(180, 50)) as pilot:
        fresh.action_asset_type("skill")
        await pilot.pause()
        assert fresh.query_one("#skill-grid", SkillGrid).row_count == 11
        fresh.save_screenshot(str(tmp_path / "post-doctor-project.svg"))
        assert_inventory(rows(project_collection))
    assert not [f for f in findings(project_collection) if f.finding_type in {
        "unlisted", "missing_canonical", "orphan_canonical", "unmanaged"}]


@pytest.mark.asyncio
async def test_unregistered_wrapper_exposure_warns_without_restore_root_advice(project_collection, tmp_path):
    home, project, backings, _ = project_collection
    convert(project_collection)
    projection("wrapper", "standard", scope="project", home=home, project=project).symlink_to(backings[1])
    app = TUIApp(cwd=project)
    app._scope = "project"
    async with app.run_test(size=(180, 50)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        assert grid.row_count == 12
        wrapper = next(r for r in rows(project_collection) if r.slug == "wrapper")
        info = grid._info_body_for_cell(
            row=wrapper, agent="standard", cell=wrapper.cells[("standard", "project")],
            pending=None, scope="project", scope_flag="-p",
        )
        assert "wrapper" in info and "whole collection" in info
        assert "Restore SKILL.md" not in info
        app.action_refresh()
        await pilot.pause()
        assert grid.row_count == 12
        app.save_screenshot(str(tmp_path / "unregistered-wrapper-warning.svg"))
