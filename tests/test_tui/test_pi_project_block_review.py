"""Issue #568: persistent npm project blocks must be explicit and reviewed."""
import json

import pytest
from rich.text import Text
from textual.widgets import Input, Static

from agent_toolkit_cli import pi_npm
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets.command_grid import CommandGrid
from tests.pi_npm_fixtures import seed_package, write_json
from tests.test_tui.test_pi_npm_controls import select, glyph


@pytest.fixture
def environment(tmp_path, monkeypatch):
    home, project = tmp_path / "home", tmp_path / "project[568]"
    home.mkdir(); project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(home / ".pi/agent"))
    monkeypatch.chdir(project)
    root = seed_package(home, project)
    write_json(project / ".pi/settings.json", {"theme": "unchanged", "extensions": ["unrelated.ts"]})
    return home, project, root


def review(app):
    # Import here so RED demonstrates missing safety behavior, not collection failure.
    from agent_toolkit_tui.screens.pi_project_blocks import PiProjectBlocksScreen
    assert isinstance(app.screen, PiProjectBlocksScreen)
    return Text.from_markup(str(app.screen.query_one("#block-review", Static).render())).plain


async def test_inherited_project_block_is_labeled_and_reviewed_across_tabs(environment):
    home, project, root = environment
    global_config = home / ".pi/agent/settings.json"
    project_config = project / ".pi/settings.json"
    before_global, before_project = global_config.read_bytes(), project_config.read_bytes()
    before_source = (root / "extensions/main.ts").read_bytes()
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, table = select(app, "project")
        await pilot.pause()
        assert "inherit" in glyph(table)
        assert "R" in str(grid.query_one("#pi-policy-help", Static).render())
        await pilot.press("space")
        assert "block" in glyph(table)
        assert grid.pending_entries() == {("project", "demo"): "unlink"}
        snapshots = grid.pending_npm_snapshots()
        app.action_scope("global")
        app.action_refresh()
        app.action_asset_type("command")
        await pilot.pause()
        assert grid.pending_npm_snapshots() == snapshots
        assert "project block" in str(app.query_one("#footer-pending", Static).render())
        await pilot.press("ctrl+s")
        await pilot.pause()
        body = review(app)
        assert "npm:demo" in body and str(project) in body
        assert str(project_config) in body
        assert "persist" in body.lower() and "inherit" in body.lower()
        assert "global" in body.lower() and "files" in body.lower()
        assert app.focused.id == "cancel"
        assert global_config.read_bytes() == before_global
        assert project_config.read_bytes() == before_project
        # Ctrl+S is not an implicit confirmation; Escape retains the draft.
        await pilot.press("ctrl+s", "escape")
        await pilot.pause()
        assert grid.pending_entries() == {("project", "demo"): "unlink"}
        assert project_config.read_bytes() == before_project
        await pilot.press("ctrl+s")
        await pilot.pause()
        review(app)
        await pilot.click("#apply-blocks")
        await pilot.pause()
        assert grid.pending_entries() == {}
        current = pi_npm.read_npm_states(home=home, project=project)["demo"]
        assert not current.project_scope.enabled
        assert current.project_scope.mode == "override"
        assert global_config.read_bytes() == before_global
        assert json.loads(project_config.read_text())["theme"] == "unchanged"
        assert json.loads(project_config.read_text())["extensions"] == ["unrelated.ts"]
        assert (root / "extensions/main.ts").read_bytes() == before_source
        grid, table = select(app, "project")
        assert "block" in glyph(table)
        await pilot.press("r")
        assert "inherit" in glyph(table)
        await pilot.press("ctrl+s")
        await pilot.pause()
        current = pi_npm.read_npm_states(home=home, project=project)["demo"]
        assert current.project_scope.mode == "inherit" and current.project_scope.enabled
        assert global_config.read_bytes() == before_global
        restored = json.loads(project_config.read_text())
        assert restored.pop("packages", []) == []
        assert restored == json.loads(before_project)
        assert (root / "extensions/main.ts").read_bytes() == before_source


@pytest.mark.parametrize("cancel_key", ["escape", "enter"])
async def test_cancel_blocks_entire_cross_kind_batch_without_losing_drafts(environment, cancel_key):
    home, project, _ = environment
    config = project / ".pi/settings.json"
    before = config.read_bytes()
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, _ = select(app, "project")
        await pilot.press("space")
        commands = app.query_one("#command-grid", CommandGrid)
        commands.restore_pending({("global", "pi", "unrelated"): "link"})
        pending = app._get_all_pending_edits()
        app.action_asset_type("command")
        await pilot.press("ctrl+s")
        await pilot.pause()
        body = review(app)
        assert "2 pending" in body
        assert "Commands" in body and "Pi Extensions" in body
        await pilot.press(cancel_key)
        await pilot.pause()
        assert app._get_all_pending_edits() == pending
        assert config.read_bytes() == before


async def test_browsing_filter_and_noop_apply_never_create_override(environment):
    _, project, _ = environment
    config = project / ".pi/settings.json"
    before = config.read_bytes()
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, _ = select(app, "project")
        app.action_focus_filter()
        await pilot.press("space")
        assert app.query_one("#pi-filter", Input).value == " "
        app.action_scope("global"); app.action_refresh()
        app.action_asset_type("command")
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert not grid.pending_entries()
        assert config.read_bytes() == before


async def test_approval_does_not_cover_a_changed_batch(environment):
    _, project, _ = environment
    config = project / ".pi/settings.json"
    before = config.read_bytes()
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, _ = select(app, "project")
        await pilot.press("space", "ctrl+s")
        await pilot.pause()
        review(app)
        app.query_one("#command-grid", CommandGrid).restore_pending({("global", "pi", "later"): "link"})
        await pilot.click("#apply-blocks")
        await pilot.pause()
        assert config.read_bytes() == before
        assert grid.pending_entries() == {("project", "demo"): "unlink"}


async def test_approved_cross_kind_batch_applies_all_intentional_drafts(environment):
    from tests.test_tui.test_command_apply import _seed

    home, project, _ = environment
    _seed(home)
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, _ = select(app, "project")
        await pilot.press("space")
        commands = app.query_one("#command-grid", CommandGrid)
        commands.restore_pending({("global", "standard", "demo"): "link"})
        app.action_asset_type("command")
        await pilot.press("ctrl+s")
        await pilot.pause()
        review(app)
        dest = home / ".claude/commands/demo.md"
        assert not dest.exists()
        # Approval is reachable without a mouse; initial Enter cancels instead.
        await pilot.press("tab", "enter")
        await pilot.pause()
        assert dest.read_text() == "demo body\n"
        assert not app._get_all_pending_edits()
        assert not pi_npm.read_npm_states(home=home, project=project)["demo"].project_scope.enabled


async def test_review_survives_package_disappearing_from_refreshed_rows(environment):
    _, project, _ = environment
    config = project / ".pi/settings.json"
    before = config.read_bytes()
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, _ = select(app, "project")
        await pilot.press("space")
        pending, snapshots = grid.pending_entries(), grid.pending_npm_snapshots()
        grid.set_rows([])
        grid.restore_pending(pending, npm_snapshots=snapshots)
        app.action_asset_type("command")
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert "npm:demo" in review(app)
        await pilot.press("escape")
        assert config.read_bytes() == before


async def test_stale_settings_fail_after_review_without_overwriting(environment):
    _, project, _ = environment
    config = project / ".pi/settings.json"
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, _ = select(app, "project")
        await pilot.press("space", "ctrl+s")
        await pilot.pause()
        review(app)
        write_json(config, {"packages": [{"source": "npm:demo@1.0.0", "extensions": []}], "theme": "new"})
        before = config.read_bytes()
        await pilot.click("#apply-blocks")
        await pilot.pause()
        assert config.read_bytes() == before
        assert grid.pending_entries() == {("project", "demo"): "unlink"}
        assert "changed" in str(app.query_one("#footer-pending", Static).render())


@pytest.mark.parametrize("size", [(80, 24), (60, 20), (40, 16)])
async def test_many_packages_are_scrollable_and_cancel_is_reachable(size, tmp_path):
    from agent_toolkit_tui.screens.pi_project_blocks import PiProjectBlocksScreen

    app = TUIApp()
    async with app.run_test(size=size) as pilot:
        app.push_screen(PiProjectBlocksScreen(
            packages=tuple(f"@scope/package-{i}" for i in range(30)),
            project=tmp_path / "[project]", settings=tmp_path / "[project]/.pi/settings.json",
            pending_count=30, asset_types=("Pi Extensions",),
        ))
        await pilot.pause()
        body = review(app)
        assert "npm:@scope/package-0" in body and "npm:@scope/package-29" in body
        from textual.containers import VerticalScroll
        scroll = app.screen.query_one(VerticalScroll)
        assert scroll.max_scroll_y > 0
        for selector in ("#cancel", "#apply-blocks"):
            button = app.screen.query_one(selector)
            assert button.region in app.screen.region
        assert app.focused.id == "cancel"
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, PiProjectBlocksScreen)


async def test_reset_inheritance_does_not_force_a_globally_disabled_package_on(environment):
    home, project, root = environment
    pi_npm.set_npm_enabled(identity="demo", enabled=False, scope="global", home=home, project=project)
    pi_npm.set_npm_enabled(identity="demo", enabled=True, scope="project", home=home, project=project)
    config = home / ".pi/agent/settings.json"
    before = config.read_bytes()
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, table = select(app, "project")
        assert "on" in glyph(table)
        await pilot.press("r")
        assert "inherit" in glyph(table)
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert not grid.pending_entries()
        state = pi_npm.read_npm_states(home=home, project=project)["demo"]
        assert state.project_scope.mode == "inherit" and not state.project_scope.enabled
        assert config.read_bytes() == before and root.exists()


async def test_multiple_blocks_including_existing_override_are_all_reviewed(environment):
    home, project, _ = environment
    seed_package(home, project, name="@scope/other")
    write_json(home / ".pi/agent/settings.json", {"packages": ["npm:demo@1.0.0", "npm:@scope/other@1.0.0"]})
    pi_npm.set_npm_enabled(identity="demo", enabled=True, scope="project", home=home, project=project)
    config = home / ".pi/agent/settings.json"
    before = config.read_bytes()
    app = TUIApp()
    async with app.run_test() as pilot:
        from textual.coordinate import Coordinate
        grid, table = select(app, "project")
        assert "on" in glyph(table)
        await pilot.press("space")
        table.cursor_coordinate = Coordinate(grid.row_slugs.index("@scope/other"), 1)
        await pilot.press("space", "ctrl+s")
        await pilot.pause()
        body = review(app)
        assert "npm:demo" in body and "npm:@scope/other" in body
        await pilot.click("#apply-blocks")
        await pilot.pause()
        states = pi_npm.read_npm_states(home=home, project=project)
        assert not grid.pending_entries()
        assert all(not states[name].project_scope.enabled for name in ("demo", "@scope/other"))
        assert config.read_bytes() == before
