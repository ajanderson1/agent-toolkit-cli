from pathlib import Path

import pytest
from textual.widgets import Static

from agent_toolkit_cli.skill_paths import library_lock_path
from agent_toolkit_tui.app import ApplyResult, TUIApp
from agent_toolkit_tui.widgets.command_grid import CommandGrid
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from tests.test_cli.test_skill_collection_reconcile import legacy


@pytest.mark.asyncio
async def test_legacy_uncheck_materializes_complete_siblings_before_wrapper_retirement(
    legacy,
):
    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=(120, 40)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        assert grid.row_count == 11
        grid.cursor_to_cell(row_slug="workflow-00", agent_name="standard")
        await pilot.press("space")
        assert grid.pending_entries() == {
            ("global", "standard", "workflow-00"): "unlink"
        }
        app.action_apply()
        await pilot.pause()
        assert grid.pending_entries() == {}
        root = Path.home() / ".agents/skills"
        assert not (root / "wrapper").exists()
        assert len(list(root.glob("workflow-*"))) == 10
        assert (root / "workflow-01").resolve() == legacy / "workflow-01"


@pytest.mark.asyncio
async def test_read_toggle_revert_noop_and_unrelated_apply_leave_legacy_untouched(
    legacy, monkeypatch
):
    before = library_lock_path().read_bytes()
    original_index = (legacy / ".git/index").read_bytes()
    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=(120, 40)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        grid.set_filter("workflow-00")
        grid.set_filter("")
        grid.cursor_to_cell(row_slug="workflow-00", agent_name="standard")
        await pilot.press("space")
        app.action_revert()
        app.action_apply()
        app._refresh_skill_view()
        commands = app.query_one("#command-grid", CommandGrid)
        commands.restore_pending({("global", "standard", "unrelated"): "link"})

        def unrelated():
            commands.clear_pending()
            return ApplyResult(
                ok=1, failed=0, errors=[], keys=[("global", "standard", "unrelated")]
            )

        monkeypatch.setattr(app, "_apply_command_pending", unrelated)
        app.action_apply()
        await pilot.pause()
    assert library_lock_path().read_bytes() == before
    assert (legacy / ".git/index").read_bytes() == original_index
    assert (Path.home() / ".agents/skills/wrapper").resolve() == legacy
    assert not list((Path.home() / ".agents/skills").glob("workflow-*"))


@pytest.mark.asyncio
async def test_cross_kind_tabs_partial_failure_retry_and_all_kind_revert(
    legacy, monkeypatch
):
    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=(120, 40)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        commands = app.query_one("#command-grid", CommandGrid)
        grid.restore_pending({("global", "standard", "workflow-00"): "unlink"})
        commands.restore_pending({("global", "standard", "other"): "link"})
        app.action_asset_type("command")
        await pilot.pause()
        app.action_asset_type("skill")
        await pilot.pause()
        assert len(app._get_all_pending_edits()) == 2
        app._refresh_skill_view()
        assert len(app._get_all_pending_edits()) == 2
        conflict = Path.home() / ".agents/skills/workflow-05"
        conflict.symlink_to(legacy / "workflow-06")
        completed = []

        def unrelated():
            completed.append("other")
            commands.clear_pending()
            return ApplyResult(
                ok=1, failed=0, errors=[], keys=[("global", "standard", "other")]
            )

        monkeypatch.setattr(app, "_apply_command_pending", unrelated)
        app.action_apply()
        await pilot.pause()
        assert completed == ["other"] and not commands.pending_entries()
        assert grid.pending_entries() == {
            ("global", "standard", "workflow-00"): "unlink"
        }
        assert "failed" in str(app.query_one("#footer-pending", Static).render())
        assert (Path.home() / ".agents/skills/wrapper").resolve() == legacy
        conflict.unlink()
        app.action_apply()
        await pilot.pause()
        assert not grid.pending_entries() and completed == ["other"]
        assert len(list((Path.home() / ".agents/skills").glob("workflow-*"))) == 10
        before = library_lock_path().read_bytes()
        grid.restore_pending({("global", "standard", "workflow-00"): "link"})
        commands.restore_pending({("global", "standard", "other"): "unlink"})
        app.action_revert()
        await pilot.pause()
        assert not app._get_all_pending_edits()
        assert library_lock_path().read_bytes() == before
