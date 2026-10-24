"""Loose selection follows native discovery/overrides; packages keep their policy."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from rich.text import Text
from textual.app import App, ComposeResult

from agent_toolkit_tui.pi_extension_state import build_pi_rows
from agent_toolkit_tui.widgets.pi_grid import PiGrid
from tests.pi_npm_fixtures import seed_package


def _settings(path: Path, **values) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values))


@pytest.mark.parametrize("scope", ["global", "project"])
@pytest.mark.parametrize("shape", ["file", "directory", "symlink"])
def test_discovered_local_extension_is_default_enabled_without_settings(
    tmp_path, monkeypatch, scope, shape,
):
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    root = home / ".pi/agent/extensions" if scope == "global" else project / ".pi/extensions"
    root.mkdir(parents=True)
    path = root / ("jev-router" if shape == "directory" else "jev-router.ts")
    if shape == "directory":
        path.mkdir()
        (path / "index.ts").write_text("export default () => {}")
    elif shape == "symlink":
        target = tmp_path / "router.ts"
        target.write_text("export default () => {}")
        path.symlink_to(target)
    else:
        path.write_text("export default () => {}")

    rows = build_pi_rows(home=home, project=project)

    assert [row.slug for row in rows] == ["jev-router"]
    row = rows[0]
    assert row.global_cell.global_loaded is (scope == "global")
    assert row.project_cell.project_loaded is True
    assert row.managed is False
    assert path.exists()


@pytest.mark.parametrize("scope,references,want", [
    ("global", ["extensions/jev-router.ts"], (True, True)),
    ("project", ["../unused.ts"], (True, True)),
    ("global", ["~/.pi/agent/extensions/jev-router.ts"], (True, True)),
    ("global", ["+extensions/jev-router.ts"], (True, True)),
    ("global", ["-extensions/jev-router.ts"], (False, False)),
    ("global", ["extensions/*.ts"], (True, True)),
    ("global", ["*.ts"], (True, True)),
    ("global", ["+extensions/*.ts"], (True, True)),
    ("global", ["extensions"], (True, True)),
    ("global", ["extensions/*.ts", "!**/jev-router.ts"], (False, False)),
    ("global", ["extensions/jev-router.ts", "-extensions/jev-router.ts"], (False, False)),
    ("global", ["extensions/jev-router.ts", "-extensions/jev-router.ts", "+extensions/jev-router.ts"], (False, False)),
])
def test_local_enablement_follows_native_selectors_and_inheritance(
    tmp_path, monkeypatch, scope, references, want,
):
    home = tmp_path / "home"
    project = tmp_path / "project"
    monkeypatch.setenv("HOME", str(home))
    path = home / ".pi/agent/extensions/jev-router.ts"
    path.parent.mkdir(parents=True)
    path.write_text("export default () => {}")
    settings = home / ".pi/agent/settings.json" if scope == "global" else project / ".pi/settings.json"
    _settings(settings, extensions=references)
    before = settings.read_bytes()

    row, = build_pi_rows(home=home, project=project)

    assert (row.global_cell.global_loaded, row.project_cell.project_loaded) == want
    assert settings.read_bytes() == before


def test_project_reference_does_not_change_global_native_selection(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "project"
    monkeypatch.setenv("HOME", str(home))
    path = home / ".pi/agent/extensions/jev-router.ts"
    path.parent.mkdir(parents=True)
    path.write_text("export default () => {}")
    settings = project / ".pi/settings.json"
    _settings(settings, extensions=[str(path)])

    row, = build_pi_rows(home=home, project=project)

    assert row.global_cell.global_loaded is True
    assert row.project_cell.project_loaded is True


@pytest.mark.parametrize("scope", ["global", "project"])
def test_legacy_npm_registration_cannot_hide_a_loose_extension(tmp_path, monkeypatch, scope):
    home = tmp_path / "home"
    project = tmp_path / "project"
    monkeypatch.setenv("HOME", str(home))
    _settings(home / ".agent-toolkit/pi-extensions-lock.json", version=1, skills={
        "context-mode": {"source": "npm:context-mode", "sourceType": "npm"},
    })
    root = home / ".pi/agent/extensions" if scope == "global" else project / ".pi/extensions"
    package = root / "context-mode"
    package.mkdir(parents=True)
    (package / "index.ts").write_text("export default () => {}")

    row, = build_pi_rows(home=home, project=project)

    assert row.origin == "untracked"
    assert row.global_cell.global_loaded is (scope == "global")
    assert row.project_cell.project_loaded is True
    assert package.is_dir()


@pytest.mark.parametrize("connection,want", [("missing", False), ("owned", True), ("foreign", False)])
def test_library_connection_requires_its_own_symlink_not_a_package_reference(
    tmp_path, monkeypatch, connection, want,
):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    _settings(home / ".agent-toolkit/pi-extensions-lock.json", version=1, skills={
        "dual": {"source": "owner/dual", "sourceType": "github"},
    })
    _settings(home / ".pi/agent/settings.json", packages=["npm:dual"])
    source = home / ".agent-toolkit/pi-extensions/dual"
    source.mkdir(parents=True)
    (source / "index.ts").write_text("export default () => {}")
    if connection != "missing":
        projection = home / ".pi/agent/extensions/dual"
        projection.parent.mkdir(parents=True)
        target = source if connection == "owned" else tmp_path / "foreign"
        target.mkdir(exist_ok=True)
        projection.symlink_to(target)

    rows = {row.slug: row for row in build_pi_rows(home=home)}
    row = rows["dual"]
    assert rows["npm:dual"].npm_state.global_scope.missing
    assert row.origin == "store-owned"
    assert row.global_cell.global_loaded is want


@pytest.mark.parametrize("global_packages,project_packages,want", [
    ([], [], None),
    (["npm:context-mode"], [], (True, True)),
    ([], [{"source": "npm:context-mode"}], (False, True)),
    (["npm:context-mode"], ["npm:context-mode"], (True, True)),
])
def test_npm_native_footprints_define_visibility_and_scope_state(
    tmp_path, monkeypatch, global_packages, project_packages, want,
):
    home = tmp_path / "home"
    project = tmp_path / "project"
    monkeypatch.setenv("HOME", str(home))
    _settings(home / ".agent-toolkit/pi-extensions-lock.json", version=1, skills={
        "context-mode": {"source": "npm:context-mode", "sourceType": "npm"},
    })
    if global_packages:
        seed_package(home, project, name="context-mode", configured=False)
    if project_packages:
        seed_package(home, project, scope="project", name="context-mode", configured=False)
    _settings(home / ".pi/agent/settings.json", packages=global_packages)
    _settings(project / ".pi/settings.json", packages=project_packages)

    rows = build_pi_rows(home=home, project=project)
    if want is None:
        assert rows == []
        return
    row, = rows

    assert row.slug == "context-mode"
    assert (row.global_cell.global_loaded, row.project_cell.project_loaded) == want


@pytest.mark.asyncio
async def test_jev_router_info_reports_native_default_enablement(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)
    path = home / ".pi/agent/extensions/jev-router.ts"
    path.parent.mkdir(parents=True)
    path.write_text("export default () => {}")
    grid = PiGrid(build_pi_rows(home=home, project=project))

    class GridApp(App):
        def compose(self) -> ComposeResult:
            yield grid

    async with GridApp().run_test() as pilot:
        grid.action_info()
        await pilot.pause()
        body = Text.from_markup(grid.app.screen._body_markup).plain
        assert "Enabled globally: Yes" in body
        assert "Enabled for this project: Yes" in body
        assert str(path) in body
        assert grid.pending_entries() == {}


@pytest.mark.asyncio
async def test_native_enabled_loose_file_counts_in_status(tmp_path, monkeypatch):
    from textual.widgets import Static
    from agent_toolkit_tui.app import TUIApp

    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(project)
    path = project / ".pi/extensions/jev-router.ts"
    path.parent.mkdir(parents=True)
    path.write_text("export default () => {}")
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("pi-extension")
        await pilot.pause()
        grid = app.query_one("#pi-grid", PiGrid)
        grid.set_rows(build_pi_rows(home=home, project=project))
        app._refresh_status_bar()
        text = Text.from_markup(str(app.query_one("#status-bar", Static).render())).plain
        assert "1 enabled" in text
