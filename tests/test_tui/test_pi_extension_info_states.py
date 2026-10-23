"""State-first Pi extension Info and scope-correct native removal guidance."""
from __future__ import annotations

import shlex

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
from agent_toolkit_tui.widgets.pi_grid import PiGrid


def _row(
    origin: str = "npm", *, slug: str = "context-mode",
    global_enabled: bool = False, project_enabled: bool = False,
    managed: bool = True,
) -> PiExtensionRow:
    cell = PiCell(global_loaded=global_enabled, project_loaded=project_enabled, origin=origin, managed=managed)
    return PiExtensionRow(
        slug=slug, origin=origin,
        source=f"npm:{slug}" if origin == "npm" else f"owner/{slug}",
        global_cell=cell, project_cell=cell, managed=managed,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("global_enabled,project_enabled", [(False, False), (True, False), (False, True), (True, True)])
async def test_info_shows_scope_enablement_without_repeating_presence(global_enabled, project_enabled):
    row = _row(global_enabled=global_enabled, project_enabled=project_enabled)
    grid = PiGrid([row])

    class _App(App):
        def compose(self) -> ComposeResult:
            yield grid

    app = _App()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = grid.query_one(DataTable)
        table.focus()
        await pilot.press("i")
        await pilot.pause()
        body = Text.from_markup(app.screen._body_markup).plain
        assert f"Enabled globally: {'Yes' if global_enabled else 'No'}" in body
        assert f"Enabled for this project: {'Yes' if project_enabled else 'No'}" in body
        assert "Registered in Toolkit" not in body
        assert "download status is not checked" not in body
        assert "No description" not in body
        assert "Ref:" not in body
        assert "loaded" not in body.lower()


@pytest.mark.asyncio
async def test_library_symlink_is_not_reported_as_settings_enablement():
    grid = PiGrid([_row("store-owned", global_enabled=True)])

    class _App(App):
        def compose(self) -> ComposeResult:
            yield grid

    async with _App().run_test() as pilot:
        grid.action_info()
        await pilot.pause()
        body = Text.from_markup(grid.app.screen._body_markup).plain
        assert "Linked globally: Yes" in body
        assert "Linked for this project: No" in body
        assert "Enabled globally" not in body


@pytest.mark.parametrize("origin", ["npm", "store-owned"])
@pytest.mark.parametrize("scope", ["global", "project"])
@pytest.mark.parametrize("enabled,pending,expected", [
    (False, None, "queue Enable"),
    (True, None, "queue Disable"),
    (False, "link", "Pending: Enable"),
    (True, "unlink", "Pending: Disable"),
])
def test_info_actions_name_enable_disable_without_claiming_package_installation(origin, scope, enabled, pending, expected):
    row = _row(origin, global_enabled=enabled, project_enabled=enabled)
    grid = PiGrid([row])
    if pending:
        grid.restore_pending({(scope, row.slug): pending})
    body = Text.from_markup(grid._info_body(row=row, scope=scope)).plain
    assert expected in body
    assert "Ctrl+S" in body
    assert "queue install" not in body
    assert "Pending: install" not in body
    assert "Pending: uninstall" not in body
    assert "loaded" not in body.lower()


@pytest.mark.parametrize("origin", ["npm", "store-owned"])
def test_project_info_explains_global_enablement_without_offering_duplicate_enable(origin):
    row = _row(origin, global_enabled=True)
    body = Text.from_markup(PiGrid([row])._info_body(row=row, scope="project")).plain
    state = "linked" if origin == "store-owned" else "enabled"
    assert f"Already {state} globally" in body
    assert "disable globally first" in body
    assert "queue Enable" not in body


@pytest.mark.parametrize("scope,managed,spec,want", [
    ("global", True, "npm:context-mode", ["pi", "uninstall", "npm:context-mode"]),
    ("project", True, "npm:context-mode", ["pi", "uninstall", "npm:context-mode", "-l"]),
    ("global", False, "npm:@scope/tools@^2", ["pi", "uninstall", "npm:@scope/tools@^2"]),
    ("project", False, "npm:@scope/tools@^3", ["pi", "uninstall", "npm:@scope/tools@^3", "-l"]),
])
def test_native_removal_uses_exact_scope_spec_and_shell_safe_arguments(scope, managed, spec, want):
    row = _row(managed=managed, global_enabled=scope == "global", project_enabled=scope == "project")
    if scope == "global":
        row.global_package_spec = spec
    else:
        row.project_package_spec = spec
    body = Text.from_markup(PiGrid([row])._info_body(row=row, scope=scope)).plain
    command = next(line.split(": ", 1)[1] for line in body.splitlines() if line.startswith("Remove with Pi:"))
    assert shlex.split(command) == want
    if managed:
        assert "Toolkit registration" in body
    else:
        assert "queue Enable" not in body


def test_unregistered_global_reference_in_project_info_has_global_removal_command():
    row = _row(managed=False, global_enabled=True)
    row.global_package_spec = "npm:context-mode@1.0.0"
    row.global_config_path = "/home/test/.pi/agent/settings.json"
    body = Text.from_markup(PiGrid([row])._info_body(row=row, scope="project")).plain
    assert "Remove with Pi: pi uninstall npm:context-mode@1.0.0\n" in body
    assert "pi uninstall npm:context-mode@1.0.0 -l" not in body
    assert "queue Enable" not in body


@pytest.mark.asyncio
async def test_pi_status_counts_enabled_configuration_not_runtime_loading():
    from textual.widgets import Static
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("pi-extension")
        await pilot.pause()
        grid = app.query_one("#pi-grid", PiGrid)
        grid.set_rows([
            _row(project_enabled=True),
            _row("store-owned", slug="library-extension", project_enabled=True),
            _row(slug="other-extension"),
        ])
        app._refresh_status_bar()
        text = Text.from_markup(str(app.query_one("#status-bar", Static).render())).plain
        assert "1 enabled" in text
        assert "1 linked" in text
        assert "loaded" not in text
