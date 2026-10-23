"""Drive real local Pi controls, not injected Info panels or library installs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from rich.text import Text
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Static

from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.pi_extension_state import build_pi_rows
from agent_toolkit_tui.widgets.pi_grid import PiGrid


@pytest.fixture
def environment(tmp_path, monkeypatch):
    home, project = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)
    return home, project


def seed(home, project, scope="global", *, directory=False):
    root = home / ".pi/agent/extensions" if scope == "global" else project / ".pi/extensions"
    path = root / ("router" if directory else "router.ts")
    path.parent.mkdir(parents=True, exist_ok=True)
    if directory:
        path.mkdir()
        (path / "a.ts").write_text("a")
        (path / "b.ts").write_text("b")
        (path / "package.json").write_text(json.dumps({"pi": {"extensions": ["a.ts", "b.ts"]}}))
    else:
        path.write_text("export default () => {}")
    return path


def select(app, scope="global", slug="router"):
    app.action_asset_type("pi-extension")
    app.action_scope(scope)
    grid = app.query_one("#pi-grid", PiGrid)
    table = grid.query_one("#pi-table", DataTable)
    table.cursor_coordinate = Coordinate(grid.row_slugs.index(slug), 1)
    table.focus()
    return grid, table


def glyph(table):
    return Text.from_markup(str(table.get_cell_at(table.cursor_coordinate))).plain


@pytest.mark.parametrize("source_scope,scope", [("global", "global"), ("global", "project"), ("project", "project")])
async def test_space_apply_refresh_and_fresh_app_disable_reenable_without_lock(environment, source_scope, scope):
    home, project = environment
    source = seed(home, project, source_scope)
    before = source.read_bytes()
    settings = home / ".pi/agent/settings.json" if scope == "global" else project / ".pi/settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"theme": "dark", "skills": ["keep"]}))
    pattern = str(source) if source_scope != scope else "extensions/router.ts"
    for initially, enabled in [(True, False), (False, True)]:
        app = TUIApp()
        async with app.run_test() as pilot:
            grid, table = select(app, scope)
            await pilot.pause()
            assert ("✔" if initially else "☐") in glyph(table)
            await pilot.press("space")
            assert grid.pending_entries() == {(scope, "router"): "link" if enabled else "unlink"}
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert grid.pending_entries() == {}
            want = ([str(source)] if source_scope != scope else []) + [("+" if enabled else "-") + pattern]
            assert json.loads(settings.read_text()) == {"theme": "dark", "skills": ["keep"], "extensions": want}
            app.action_refresh()
            await pilot.pause()
            assert ("✔" if enabled else "☐") in glyph(table)
            row, = build_pi_rows(home=home, project=project)
            assert row.origin == "untracked" and not row.managed
            if source_scope == "global" and scope == "project":
                assert row.global_cell.global_loaded is True
    app = TUIApp()
    async with app.run_test() as pilot:
        _, table = select(app, scope)
        await pilot.pause()
        assert "✔" in glyph(table)
    assert source.read_bytes() == before
    assert not (home / ".agent-toolkit/pi-extensions-lock.json").exists()
    assert not (project / ".agent-toolkit/pi-extensions-lock.json").exists()


async def test_scope_switch_and_refresh_keep_the_original_target_snapshot(environment):
    home, project = environment
    source = seed(home, project)
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, _ = select(app)
        await pilot.press("space")
        assert grid.pending_entries() == {("global", "router"): "unlink"}
        app.action_scope("project")
        app.action_scope("global")
        source.with_suffix(".js").write_text("new entrypoint")
        app.action_refresh()
        await pilot.pause()
        assert grid.pending_entries() == {("global", "router"): "unlink"}
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert grid.pending_entries() == {("global", "router"): "unlink"}
        footer = str(app.query_one("#footer-pending", Static).render())
        assert "apply failed" in footer and "changed" in footer
        assert not (home / ".pi/agent/settings.json").exists()
        app.action_revert()
        assert grid.pending_entries() == {}


@pytest.mark.parametrize("failure", ["malformed", "invalid-utf8", "vanished", "busy", "partial-directory"])
async def test_failed_apply_keeps_intent_without_mutating_settings_or_crashing(environment, failure):
    home, project = environment
    source = seed(home, project, directory=failure == "partial-directory")
    settings = home / ".pi/agent/settings.json"
    settings.write_text(json.dumps({"theme": "dark"}))
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, _ = select(app)
        await pilot.press("space")
        assert grid.pending_entries() == {("global", "router"): "unlink"}
        if failure == "malformed":
            settings.write_text("{broken")
        elif failure == "invalid-utf8":
            settings.write_bytes(b"\xff")
        elif failure == "vanished":
            source.unlink()
        elif failure == "busy":
            Path(str(settings) + ".lock").mkdir()
        else:
            (source / "a.ts").unlink()
        before = settings.read_bytes()
        app.action_refresh()
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert grid.pending_entries() == {("global", "router"): "unlink"}
        assert settings.read_bytes() == before
        assert "apply failed" in str(app.query_one("#footer-pending", Static).render())


async def test_mixed_directory_shows_partial_state_and_space_enables_every_entry(environment):
    home, project = environment
    source = seed(home, project, directory=True)
    settings = home / ".pi/agent/settings.json"
    settings.write_text(json.dumps({"extensions": ["-extensions/router/a.ts"]}))
    before = settings.read_bytes()
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, table = select(app)
        assert "◐" in glyph(table)
        await pilot.press("i")
        await pilot.pause()
        body = Text.from_markup(app.screen._body_markup).plain
        assert "Mixed (1/2)" in body
        assert "all 2 entrypoints" in body
        assert str(source / "a.ts") in body and str(source / "b.ts") in body
        await pilot.press("escape")
        app.action_refresh()
        assert settings.read_bytes() == before
        table.focus()
        await pilot.press("space", "ctrl+s")
        await pilot.pause()
        assert "✔" in glyph(table)
        assert json.loads(settings.read_text())["extensions"] == ["+extensions/router/a.ts", "+extensions/router/b.ts"]
        assert grid.pending_entries() == {}
        assert (source / "a.ts").read_text() == "a" and (source / "b.ts").read_text() == "b"


async def test_partial_success_keeps_only_the_failed_local_intent(environment):
    home, project = environment
    seed(home, project)
    second = home / ".pi/agent/extensions/second.ts"
    second.write_text("second")
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, _ = select(app)
        await pilot.press("space")
        select(app, slug="second")
        await pilot.press("space")
        second.unlink()
        result = app._apply_pi_pending()
        await pilot.pause()
        assert result.ok == 1 and result.failed == 1
        assert grid.pending_entries() == {("global", "second"): "unlink"}
        assert json.loads((home / ".pi/agent/settings.json").read_text())["extensions"] == ["-extensions/router.ts"]


async def test_refresh_preserves_local_intent_but_keeps_registered_package_discard_policy(environment):
    home, project = environment
    seed(home, project)
    lock = home / ".agent-toolkit/pi-extensions-lock.json"
    lock.parent.mkdir(parents=True)
    lock.write_text(json.dumps({"version": 1, "skills": {"registered": {"source": "npm:registered", "sourceType": "npm"}}}))
    before = lock.read_bytes()
    app = TUIApp()
    async with app.run_test() as pilot:
        grid, _ = select(app, slug="registered")
        await pilot.press("space")
        select(app)
        await pilot.press("space")
        assert grid.pending_entries() == {("global", "registered"): "link", ("global", "router"): "unlink"}
        app.action_refresh()
        await pilot.pause()
        assert grid.pending_entries() == {("global", "router"): "unlink"}
        assert lock.read_bytes() == before
