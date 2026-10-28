"""State-first native npm Info; removal never silently switches scope."""
from dataclasses import replace
import shlex

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from agent_toolkit_cli._pi_settings import npm_identity
from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
from agent_toolkit_tui.widgets.pi_grid import PiGrid
from tests.pi_npm_fixtures import display_state


def _row(origin="npm", *, slug="context-mode", global_enabled=False, project_enabled=False, managed=True):
    cell = PiCell(global_loaded=global_enabled, project_loaded=project_enabled, origin=origin, managed=managed)
    return PiExtensionRow(slug=slug, origin=origin,
        source=f"npm:{slug}" if origin == "npm" else f"owner/{slug}",
        global_cell=cell, project_cell=cell, managed=managed,
        npm_state=display_state(slug, global_enabled, project_enabled) if origin == "npm" else None)


@pytest.mark.parametrize("global_enabled,project_enabled", [(False, False), (True, False), (False, True), (True, True)])
async def test_info_shows_scope_enablement_without_repeating_presence(global_enabled, project_enabled):
    grid = PiGrid([_row(global_enabled=global_enabled, project_enabled=project_enabled)])
    class GridApp(App):
        def compose(self) -> ComposeResult:
            yield grid
    async with GridApp().run_test() as pilot:
        grid.query_one(DataTable).focus()
        await pilot.press("i"); await pilot.pause()
        body = Text.from_markup(grid.app.screen._body_markup).plain
        expected = "Enabled" if global_enabled else "Disabled"
        assert f"State:  {expected}" in body
        assert f"Enabled globally: {'Enabled' if global_enabled else 'Disabled'}" in body
        assert f"Enabled for this project: {'Enabled' if project_enabled else 'Disabled'}" in body
        assert "Registered in Toolkit" not in body
        assert "download status is not checked" not in body
        assert "No description" not in body and "Ref:" not in body
        assert "loaded" not in body.lower()


async def test_library_symlink_is_not_reported_as_settings_enablement():
    grid = PiGrid([_row("store-owned", global_enabled=True)])
    class GridApp(App):
        def compose(self) -> ComposeResult:
            yield grid
    async with GridApp().run_test() as pilot:
        grid.action_info(); await pilot.pause()
        body = Text.from_markup(grid.app.screen._body_markup).plain
        assert "State:  Linked: Yes" in body
        assert "Linked globally: Yes" in body
        assert "Linked for this project: No" in body
        assert "Enabled globally" not in body


@pytest.mark.parametrize("origin", ["npm", "store-owned"])
@pytest.mark.parametrize("scope", ["global", "project"])
@pytest.mark.parametrize("enabled,pending,expected", [(False, None, "queue Enable"), (True, None, "queue Disable"), (False, "link", "Pending: Enable"), (True, "unlink", "Pending: Disable")])
def test_info_names_settings_actions_not_installation(origin, scope, enabled, pending, expected):
    row = _row(origin, global_enabled=enabled, project_enabled=enabled)
    grid = PiGrid([row])
    if pending:
        grid.restore_pending({(scope, row.slug): pending})
    body = Text.from_markup(grid._info_body(row=row, scope=scope)).plain
    assert expected in body and "Ctrl+S" in body
    assert "queue install" not in body and "Pending: uninstall" not in body
    assert "loaded" not in body.lower()


def test_library_project_info_keeps_existing_global_link_guard():
    row = _row("store-owned", global_enabled=True)
    body = Text.from_markup(PiGrid([row])._info_body(row=row, scope="project")).plain
    assert "Already linked globally" in body and "disable globally first" in body
    assert "queue Enable" not in body


@pytest.mark.parametrize("scope,managed,spec", [("global", True, "npm:context-mode"), ("project", True, "npm:context-mode"), ("global", False, "npm:@scope/tools@^2"), ("project", False, "npm:@scope/tools@^3")])
def test_removal_names_scope_identity_and_confirmation_aware_cli(scope, managed, spec):
    identity = npm_identity(spec)
    row = _row(slug=identity, managed=managed, global_enabled=scope == "global", project_enabled=scope == "project")
    selected = replace(row.npm_state.for_scope(scope), record=spec, source=spec, mode="owned")
    row.npm_state = replace(row.npm_state, **{"global_scope" if scope == "global" else "project_scope": selected})
    body = Text.from_markup(PiGrid([row])._info_body(row=row, scope=scope)).plain
    command = next(line.split(": ", 1)[1] for line in body.splitlines() if line.startswith("Remove installation/declaration:"))
    assert shlex.split(command) == ["agent-toolkit-cli", "pi-extensions", "remove", "npm:" + identity, "--" + scope]
    assert "registration is kept" not in body
    assert "no separate" not in body.lower()


def test_project_inheritance_never_suggests_silently_uninstalling_globally():
    row = _row(managed=False, global_enabled=True, project_enabled=True)
    body = Text.from_markup(PiGrid([row])._info_body(row=row, scope="project")).plain
    assert "Inherited global policy" in body
    assert "Disable here" in body
    assert "Remove installation/declaration:" not in body
    assert "disable globally first" not in body


async def test_pi_status_counts_enabled_configuration_not_runtime_loading():
    from textual.widgets import Static
    from agent_toolkit_tui.app import TUIApp
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("pi-extension"); await pilot.pause()
        grid = app.query_one("#pi-grid", PiGrid)
        grid.set_rows([_row(project_enabled=True), _row("store-owned", slug="library-extension", project_enabled=True), _row(slug="other-extension")])
        app._refresh_status_bar()
        text = Text.from_markup(str(app.query_one("#status-bar", Static).render())).plain
        assert "1 enabled" in text and "1 linked" in text
        assert "loaded" not in text
