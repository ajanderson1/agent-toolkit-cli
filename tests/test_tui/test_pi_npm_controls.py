"""Actual npm Space/Apply/refresh/reset controls with native Pi state."""
import json

import pytest
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Static
from rich.text import Text

from agent_toolkit_cli import pi_npm
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.pi_extension_state import build_pi_rows
from agent_toolkit_tui.widgets.pi_grid import PiGrid
from tests.pi_npm_fixtures import seed_package, write_json


@pytest.fixture
def environment(tmp_path, monkeypatch):
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir(); project.mkdir()
    monkeypatch.setenv("HOME", str(home)); monkeypatch.chdir(project)
    root = seed_package(home, project)
    return home, project, root


def select(app, scope="global"):
    app.action_asset_type("pi-extension"); app.action_scope(scope)
    grid = app.query_one("#pi-grid", PiGrid)
    table = grid.query_one("#pi-table", DataTable)
    table.cursor_coordinate = Coordinate(grid.row_slugs.index("demo"), 1)
    table.focus()
    return grid, table


def glyph(table):
    return Text.from_markup(str(table.get_cell_at(table.cursor_coordinate))).plain


@pytest.mark.parametrize("scope", ["global", "project"])
async def test_space_apply_refresh_fresh_app_without_registration(environment, scope):
    home, project, root = environment
    global_config = home / ".pi/agent/settings.json"
    before_global = global_config.read_bytes()
    before_source = (root / "extensions/main.ts").read_bytes()
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, table = select(app, scope)
        await pilot.pause()
        assert "✔" in glyph(table)
        await pilot.press("space")
        assert grid.pending_entries() == {(scope, "demo"): "unlink"}
        await pilot.press("ctrl+s"); await pilot.pause()
        assert grid.pending_entries() == {}
        current = pi_npm.read_npm_states(home=home, project=project)["demo"]
        assert not current.for_scope(scope).enabled
        assert current.for_scope(scope).configured
        if scope == "project":
            assert global_config.read_bytes() == before_global
            assert not (project / ".pi/npm").exists()
        app.action_refresh(); await pilot.pause()
        assert "☐" in glyph(table)
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, table = select(app, scope)
        await pilot.pause(); assert "☐" in glyph(table)
        await pilot.press("space", "ctrl+s"); await pilot.pause()
        assert grid.pending_entries() == {}
        assert pi_npm.read_npm_states(home=home, project=project)["demo"].for_scope(scope).enabled
    assert (root / "extensions/main.ts").read_bytes() == before_source
    assert not (home / ".agent-toolkit/pi-extensions-lock.json").exists()


async def test_native_draft_survives_refresh_scope_and_rejects_changed_filters(environment):
    home, project, root = environment
    config = home / ".pi/agent/settings.json"
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, table = select(app)
        await pilot.press("space")
        snapshot = grid.pending_npm_snapshots()
        app.action_scope("project"); app.action_scope("global"); app.action_refresh()
        await pilot.pause()
        assert grid.pending_entries() == {("global", "demo"): "unlink"}
        assert grid.pending_npm_snapshots() == snapshot
        write_json(config, {"packages": [{"source": "npm:demo@1.0.0", "extensions": []}]})
        before = config.read_bytes()
        await pilot.press("ctrl+s"); await pilot.pause()
        assert config.read_bytes() == before
        assert grid.pending_entries() == {("global", "demo"): "unlink"}
        assert "changed" in str(app.query_one("#footer-pending", Static).render())
        app.action_revert()
        assert grid.pending_entries() == {}


async def test_project_reset_key_restores_global_default_without_uninstall(environment):
    home, project, root = environment
    pi_npm.set_npm_enabled(identity="demo", enabled=False, scope="project", home=home, project=project)
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, table = select(app, "project")
        await pilot.press("r")
        assert grid.pending_entries() == {("project", "demo"): "reset"}
        await pilot.press("ctrl+s"); await pilot.pause()
        assert grid.pending_entries() == {}
        current = pi_npm.read_npm_states(home=home, project=project)["demo"]
        assert current.project_scope.enabled and current.project_scope.mode == "inherit"
        assert root.exists()


async def test_mixed_package_space_enables_all_and_info_is_native(environment):
    home, project, root = environment
    manifest = json.loads((root / "package.json").read_text())
    manifest["pi"]["extensions"].append("extensions/second.ts")
    (root / "extensions/second.ts").write_text("throw new Error('never execute')")
    write_json(root / "package.json", manifest)
    write_json(home / ".pi/agent/settings.json", {"packages": [{"source": "npm:demo@1.0.0", "extensions": ["-extensions/main.ts"]}]})
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, table = select(app)
        await pilot.pause(); assert "◐" in glyph(table)
        app._refresh_status_bar()
        assert "1 mixed" in Text.from_markup(str(app.query_one("#status-bar", Static).render())).plain
        info = grid._info_body(row=grid._rows[grid.row_slugs.index("demo")], scope="global")
        assert "not registered" not in info and "registration is kept" not in info
        assert "1.0.0" in info and str(root) in info
        await pilot.press("space", "ctrl+s"); await pilot.pause()
        assert grid.pending_entries() == {}
        assert pi_npm.read_npm_states(home=home, project=project)["demo"].global_scope.enabled
