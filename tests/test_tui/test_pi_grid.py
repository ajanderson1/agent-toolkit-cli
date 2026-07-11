"""Pilot tests for the PiGrid widget and the pi-extension TUI flow.

Covers:
- grid mounts with correct columns
- row count
- toggle global/project queues link
- toggle-twice clears
- npm row toggles both scopes
- untracked row is non-interactive no-op
- PendingChanged fires
- apply store-owned global (monkeypatch apply)
- apply npm global + project (monkeypatch add_package, assert scope/project args)
- apply store-owned project writes project lock
- apply InstallError surfaces notify + footer
- apply PiSettingsError surfaces notify + footer
- asset-type sidebar lists both asset types
- switch-to-pi shows PiGrid
- switch-to-skill shows SkillGrid
- existing skill TUI tests still pass (separate file)
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from rich.text import Text
from textual.events import Resize
from textual.geometry import Size
from textual.widgets import DataTable, OptionList, Static

from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
from agent_toolkit_tui.widgets.pi_grid import PiGrid
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store_row(
    slug: str,
    *,
    global_loaded: bool = False,
    project_loaded: bool = False,
) -> PiExtensionRow:
    cell = PiCell(
        global_loaded=global_loaded,
        project_loaded=project_loaded,
        origin="store-owned",
    )
    return PiExtensionRow(
        slug=slug,
        origin="store-owned",
        source=f"git@github.com:x/{slug}",
        global_cell=cell,
        project_cell=cell,
    )


def _npm_row(
    slug: str,
    *,
    global_loaded: bool = False,
    project_loaded: bool = False,
) -> PiExtensionRow:
    spec = f"npm:{slug}"
    cell = PiCell(
        global_loaded=global_loaded,
        project_loaded=project_loaded,
        origin="npm",
    )
    return PiExtensionRow(
        slug=slug,
        origin="npm",
        source=spec,
        global_cell=cell,
        project_cell=cell,
    )


def _unmanaged_npm_row(slug: str) -> PiExtensionRow:
    spec = f"npm:{slug}"
    cell = PiCell(
        global_loaded=True,
        project_loaded=False,
        origin="npm",
        managed=False,
        package_spec=spec,
        config_path="/tmp/home/.pi/agent/settings.json",
    )
    return PiExtensionRow(
        slug=slug,
        origin="npm",
        source=spec,
        global_cell=cell,
        project_cell=cell,
        managed=False,
        global_config_path="/tmp/home/.pi/agent/settings.json",
        global_package_spec=spec,
    )


def _untracked_row(slug: str) -> PiExtensionRow:
    cell = PiCell(global_loaded=True, project_loaded=False, origin="untracked")
    return PiExtensionRow(
        slug=slug,
        origin="untracked",
        source="local",
        global_cell=cell,
        project_cell=cell,
    )


# ---------------------------------------------------------------------------
# PiGrid unit tests (widget-level)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pi_grid_mounts_with_single_scope_column():
    """Grid shows EXTENSION, Pi, Origin, Source — 4 columns. The header
    carries NO scope name (the ScopeToggle communicates scope, matching the
    other asset-type tabs, #349)."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#pi-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert len(labels) == 4
        assert "Pi Extension ⓘ" in labels
        assert not any("EXTENSION" in label for label in labels)
        assert not any("Hermes" in label for label in labels)
        assert any(lbl.startswith("Pi ") for lbl in labels)
        assert not any("global" in lbl.lower() for lbl in labels)
        assert not any("project" in lbl.lower() for lbl in labels)
        assert any("Origin" in lbl for lbl in labels)
        assert any("Source" in lbl for lbl in labels)


@pytest.mark.asyncio
async def test_pi_grid_extension_column_uses_available_width_and_ellipsis():
    """Long extension names should not hard-clip while spare pane width exists."""

    long_slug = "@juicesharp/rpiv-ask-user-question"

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_npm_row(long_slug)], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)

        grid.on_resize(Resize(Size(140, 30), Size(100, 30)))
        await pilot.pause()

        extension_key = list(table.columns.keys())[0]
        assert table.columns[extension_key].width >= len(long_slug)

        cell = table.get_cell_at(Coordinate(0, 0))
        assert isinstance(cell, Text)
        assert cell.overflow == "ellipsis"
        assert cell.no_wrap is True

@pytest.mark.asyncio
async def test_pi_grid_resize_shrinks_source_column_to_remaining_width():
    """Resize keeps passive Source column inside available table width."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)

        grid.on_resize(Resize(Size(72, 20), Size(72, 20)))
        assert list(table.columns.values())[-1].width == 22

        grid.on_resize(Resize(Size(40, 20), Size(40, 20)))
        assert list(table.columns.values())[-1].width == 10


@pytest.mark.asyncio
async def test_pi_grid_store_origin_uses_library_copy():
    """Visible origin copy says library, never store."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#pi-table", DataTable)
        cells = [str(cell) for cell in table.get_row_at(0)]
        assert any("library" in cell for cell in cells)
        assert not any("store" in cell.lower() for cell in cells)


@pytest.mark.asyncio
async def test_pi_grid_origin_and_extension_info_use_library_copy():
    """Info surfaces translate internal store-owned enum to library wording."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", PiGrid)
        row = _store_row("alpha")

        origin_body = grid._origin_info_body()
        assert "library-owned" in origin_body
        assert "agent-toolkit library" in origin_body
        assert "Store path" not in origin_body
        assert "store-owned" not in origin_body

        extension_body = grid._extension_info_body(row)
        assert "Origin: library" in extension_body
        assert "Library path:" in extension_body
        assert "Store path:" not in extension_body
        assert "store-owned" not in extension_body

        table = app.query_one("#pi-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=0)
        table.focus()
        await pilot.press("i")
        await pilot.pause()
        assert "Origin: library" in app.screen._body_markup
        assert "Store path" not in app.screen._body_markup
        assert "store-owned" not in app.screen._body_markup


@pytest.mark.asyncio
async def test_pi_grid_set_scope_clears_pending_and_snaps_cursor():
    """set_scope clears pending (uniform widget contract — preservation is
    the app's job) and snaps the cursor to the scope column (#349)."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {("global", "alpha"): "link"}

        # Park the cursor on Origin (old project-column index) to prove the snap.
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        g.set_scope("project")
        g.set_rows([_store_row("alpha")])  # app always refreshes after set_scope
        await pilot.pause()
        assert g.pending_entries() == {}
        # Cursor snapped to the scope column — without the snap a cursor on the
        # removed project column lands on non-interactive Origin (#349 review).
        assert table.cursor_coordinate.column == 1


@pytest.mark.asyncio
async def test_pi_grid_globe_indicator_in_project_scope():
    """Project scope shows the 🌐 indicator on rows loaded globally, matching
    the skill grid's global indicator; global scope never shows it (#349)."""
    from textual.coordinate import Coordinate

    def _rows():
        return [
            _store_row("alpha", global_loaded=True, project_loaded=False),
            _store_row("beta", global_loaded=False, project_loaded=False),
        ]

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid(_rows(), id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)

        # Global scope (default): alpha renders loaded, NO globe anywhere.
        assert "✔" in str(table.get_cell_at(Coordinate(0, 1)))
        assert "🌐" not in str(table.get_cell_at(Coordinate(0, 1)))

        g.set_scope("project")
        g.set_rows(_rows())
        await pilot.pause()
        # Project scope: alpha is unloaded here but loaded globally → ☐ 🌐.
        alpha_cell = str(table.get_cell_at(Coordinate(0, 1)))
        assert "☐" in alpha_cell and "🌐" in alpha_cell
        # beta is loaded nowhere → no globe.
        assert "🌐" not in str(table.get_cell_at(Coordinate(1, 1)))


@pytest.mark.asyncio
async def test_pi_grid_row_count():
    """Row count equals the number of rows passed in."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("a"), _store_row("b"), _store_row("c")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        assert g.row_count == 3
        assert g.row_slugs == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_toggle_global_queues_link():
    """Space on a global cell with unloaded store-owned row queues 'link'."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("alpha", global_loaded=False)], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        # Column 1 = Pi (global)
        table = app.query_one("#pi-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {("global", "alpha"): "link"}


@pytest.mark.asyncio
async def test_toggle_project_queues_link():
    """Space on the scope cell in project scope queues 'link' (#349)."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("alpha", project_loaded=False)], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        g.set_scope("project")
        g.set_rows([_store_row("alpha", project_loaded=False)])
        table = app.query_one("#pi-table", DataTable)
        # Column 1 = Pi (<active scope>)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {("project", "alpha"): "link"}


@pytest.mark.asyncio
async def test_toggle_loaded_queues_unlink():
    """Space on a loaded global cell queues 'unlink'."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("alpha", global_loaded=True)], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {("global", "alpha"): "unlink"}


@pytest.mark.asyncio
async def test_toggle_twice_clears_pending():
    """Toggle twice returns to empty pending."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("alpha", global_loaded=False)], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.press("space")
        assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_npm_row_toggles_per_scope():
    """npm row: each scope queues its own op via the single scope column;
    set_scope clears the queue (uniform widget contract, #349)."""

    def _rows():
        return [_npm_row("@scope/pkg", global_loaded=False, project_loaded=True)]

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid(_rows(), id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)

        # Global scope (default): toggle → link, key is global.
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {("global", "@scope/pkg"): "link"}

        # Scope switch clears the queue.
        g.set_scope("project")
        g.set_rows(_rows())
        await pilot.pause()
        assert g.pending_entries() == {}

        # Project scope: toggle → unlink (already loaded), key is project.
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {("project", "@scope/pkg"): "unlink"}


@pytest.mark.asyncio
async def test_unmanaged_npm_row_is_non_interactive_and_labeled():
    """Space on unmanaged npm warns/no-ops; origin says npm unmanaged."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_unmanaged_npm_row("pi-title-renamer")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)
        assert "npm unmanaged" in str(table.get_cell_at(Coordinate(0, 2)))
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_unmanaged_npm_info_body_gives_manual_removal_advice():
    """Info body explains toolkit refusal and exact settings edit."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_unmanaged_npm_row("pi-title-renamer")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        row = _unmanaged_npm_row("pi-title-renamer")
        body = g._info_body(row=row, scope="global")
        assert "unmanaged npm package" in body
        assert "will not remove packages it did not add" in body
        assert "/tmp/home/.pi/agent/settings.json" in body
        assert 'remove "npm:pi-title-renamer" from packages[]' in body

        # If the active scope has no npm metadata, still show the exact loaded
        # scope path/spec instead of a vague placeholder.
        project_body = g._info_body(row=row, scope="project")
        assert "/tmp/home/.pi/agent/settings.json" in project_body
        assert 'remove "npm:pi-title-renamer" from packages[]' in project_body


@pytest.mark.asyncio
async def test_untracked_row_is_non_interactive():
    """Space on an untracked row has no effect."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_untracked_row("loose-ext")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)
        # Try toggling the global column
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        # Must remain empty
        assert g.pending_entries() == {}


def test_pending_changed_message_carries_count():
    msg = PiGrid.PendingChanged(5)
    assert msg.count == 5


@pytest.mark.asyncio
async def test_pending_changed_fires_on_toggle():
    """PendingChanged is posted when a cell is toggled."""
    received: list[int] = []

    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_store_row("alpha")], id="g")

        def on_pi_grid_pending_changed(self, event: PiGrid.PendingChanged) -> None:
            received.append(event.count)

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#pi-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

    assert 1 in received


# ---------------------------------------------------------------------------
# Apply tests (via TUIApp with monkeypatching)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_store_owned_global(monkeypatch):
    """Apply a global store-owned link: calls pi_extension_install.apply."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.pi_extension_install as _pi_install
    import agent_toolkit_cli.pi_extension_lock as _lock
    import agent_toolkit_cli.pi_extension_ops as _ops

    applied_calls: list[Any] = []

    def fake_plan(*, slug, scope, action, home=None, project=None):
        return MagicMock(is_noop=lambda: False)

    def fake_apply(p, *, home=None, project=None):
        applied_calls.append((p, scope, home, project))

    entry = MagicMock()
    entry.source_type = "git"
    entry.source = "git@github.com:x/alpha"
    entry.ref = "main"
    entry.pi_extension_path = None

    def fake_read_lock(path):
        lf = MagicMock()
        lf.skills = {"alpha": entry}
        return lf

    monkeypatch.setattr(_pi_install, "plan", fake_plan)
    monkeypatch.setattr(_pi_install, "apply", fake_apply)
    monkeypatch.setattr(_lock, "read_lock", fake_read_lock)
    # The app reads the global lock to learn the slug universe; the delegated
    # core (pi_extension_ops) re-reads its own entry via _global_entry.
    monkeypatch.setattr(_ops, "_global_entry", lambda slug: entry)
    monkeypatch.setattr("agent_toolkit_cli.pi_extension_paths.library_lock_path", lambda env=None: Path("/fake/lock"))

    scope = "global"

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_asset_type = "pi-extension"
        grid = app.query_one("#pi-grid", PiGrid)
        grid.set_rows([_store_row("alpha", global_loaded=False)])
        grid.restore_pending({("global", "alpha"): "link"})
        await pilot.pause()

        app._apply_pi_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "applied:" in footer
    assert "failed" not in footer or "0 failed" in footer
    assert len(applied_calls) >= 1


@pytest.mark.asyncio
async def test_apply_npm_global_and_project(monkeypatch):
    """Apply npm link for global and unlink for project: delegates to
    add_package (link) and remove_package_by_identity (unlink, drift-tolerant)."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli._pi_settings as _settings
    import agent_toolkit_cli.pi_extension_lock as _lock
    import agent_toolkit_cli.pi_extension_ops as _ops

    add_calls: list[Any] = []
    remove_calls: list[Any] = []

    def fake_add(spec, *, scope, home=None, project=None):
        add_calls.append({"spec": spec, "scope": scope, "home": home, "project": project})

    def fake_remove(spec, *, scope, home=None, project=None):
        remove_calls.append({"spec": spec, "scope": scope, "home": home, "project": project})

    entry = MagicMock()
    entry.source_type = "npm"
    entry.source = "npm:@scope/pkg"
    entry.ref = None
    entry.pi_extension_path = None

    def fake_read_lock(path):
        lf = MagicMock()
        lf.skills = {"@scope/pkg": entry}
        return lf

    monkeypatch.setattr(_settings, "add_package", fake_add)
    # Delegated npm uninstall goes through remove_package_by_identity (#333):
    # drift-tolerant, unlike the old exact-match remove_package.
    monkeypatch.setattr(_settings, "remove_package_by_identity", fake_remove)
    monkeypatch.setattr(_lock, "read_lock", fake_read_lock)
    monkeypatch.setattr(_ops, "_global_entry", lambda slug: entry)
    monkeypatch.setattr("agent_toolkit_cli.pi_extension_paths.library_lock_path", lambda env=None: Path("/fake/lock"))

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_asset_type = "pi-extension"
        grid = app.query_one("#pi-grid", PiGrid)
        grid.set_rows([_npm_row("@scope/pkg", global_loaded=False, project_loaded=True)])
        grid.restore_pending({
            ("global", "@scope/pkg"): "link",
            ("project", "@scope/pkg"): "unlink",
        })
        await pilot.pause()

        app._apply_pi_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "applied:" in footer
    # add_package called for global scope
    assert any(c["scope"] == "global" and c["spec"] == "npm:@scope/pkg" for c in add_calls)
    # remove_package_by_identity called for project scope
    assert any(c["scope"] == "project" and c["spec"] == "npm:@scope/pkg" for c in remove_calls)


@pytest.mark.asyncio
async def test_apply_store_owned_project_writes_lock(monkeypatch, tmp_path):
    """Project store-owned apply: lock file updated after successful projection."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.pi_extension_install as _pi_install
    import agent_toolkit_cli.pi_extension_lock as _lock
    import agent_toolkit_cli.pi_extension_ops as _ops
    from agent_toolkit_cli.skill_lock import LockFile

    proj_lock = LockFile(version=1, skills={})

    def fake_plan(*, slug, scope, action, home=None, project=None):
        return MagicMock(is_noop=lambda: False)

    def fake_apply_proj(p, *, home=None, project=None):
        pass  # success

    written: list[Any] = []

    entry = MagicMock()
    entry.source_type = "git"
    entry.source = "git@github.com:x/alpha"
    entry.ref = "main"
    entry.pi_extension_path = None

    def fake_read_lock(path):
        if "projects" in str(path) or ".pi-extension-lock" in str(path):
            return proj_lock
        lf = MagicMock()
        lf.skills = {"alpha": entry}
        return lf

    def fake_write_lock(path, lockfile):
        written.append((path, lockfile))

    def fake_add_entry(lf, slug, entry):
        new = LockFile(version=1, skills={**lf.skills, slug: entry})
        return new

    def fake_lock_file_path(*, scope, home=None, project=None):
        return tmp_path / ".pi-extension-lock.json"

    monkeypatch.setattr(_pi_install, "plan", fake_plan)
    monkeypatch.setattr(_pi_install, "apply", fake_apply_proj)
    monkeypatch.setattr(_lock, "read_lock", fake_read_lock)
    monkeypatch.setattr(_lock, "write_lock", fake_write_lock)
    monkeypatch.setattr(_lock, "add_entry", fake_add_entry)
    # The project-lock bookkeeping after projection now lives in the delegated
    # core (pi_extension_ops), which binds these names at import — patch them
    # there too so the project write is observed (#333).
    monkeypatch.setattr(_ops, "_global_entry", lambda slug: entry)
    monkeypatch.setattr(_ops, "read_lock", fake_read_lock)
    monkeypatch.setattr(_ops, "write_lock", fake_write_lock)
    monkeypatch.setattr(_ops, "add_entry", fake_add_entry)
    monkeypatch.setattr(_ops, "lock_file_path", fake_lock_file_path)
    monkeypatch.setattr("agent_toolkit_cli.pi_extension_paths.library_lock_path", lambda env=None: Path("/fake/lock"))
    monkeypatch.setattr("agent_toolkit_cli.pi_extension_paths.lock_file_path", fake_lock_file_path)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_asset_type = "pi-extension"
        grid = app.query_one("#pi-grid", PiGrid)
        grid.set_rows([_store_row("alpha", project_loaded=False)])
        grid.restore_pending({("project", "alpha"): "link"})
        await pilot.pause()

        app._apply_pi_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "applied:" in footer
    # write_lock should have been called for the project lock
    assert written, "expected write_lock to be called for project lock"


@pytest.mark.asyncio
async def test_apply_install_error_surfaces_notify_and_footer(monkeypatch):
    """InstallError from pi_extension_install.apply must surface via notify + footer."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.pi_extension_install as _pi_install
    import agent_toolkit_cli.pi_extension_lock as _lock
    import agent_toolkit_cli.pi_extension_ops as _ops

    notify_calls: list[Any] = []

    def fake_plan(*, slug, scope, action, home=None, project=None):
        return MagicMock(is_noop=lambda: False)

    def fake_apply_err(p, *, home=None, project=None):
        raise _pi_install.InstallError("symlink conflict at /fake/path")

    entry = MagicMock()
    entry.source_type = "git"
    entry.source = "git@github.com:x/alpha"
    entry.ref = "main"
    entry.pi_extension_path = None

    def fake_read_lock(path):
        lf = MagicMock()
        lf.skills = {"alpha": entry}
        return lf

    monkeypatch.setattr(_pi_install, "plan", fake_plan)
    monkeypatch.setattr(_pi_install, "apply", fake_apply_err)
    monkeypatch.setattr(_lock, "read_lock", fake_read_lock)
    monkeypatch.setattr(_ops, "_global_entry", lambda slug: entry)
    monkeypatch.setattr("agent_toolkit_cli.pi_extension_paths.library_lock_path", lambda env=None: Path("/fake/lock"))

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        orig_notify = app.notify

        def spy_notify(*a, **k):
            notify_calls.append(k)
            return orig_notify(*a, **k)

        monkeypatch.setattr(app, "notify", spy_notify)
        app._active_asset_type = "pi-extension"
        grid = app.query_one("#pi-grid", PiGrid)
        grid.set_rows([_store_row("alpha", global_loaded=False)])
        grid.restore_pending({("global", "alpha"): "link"})
        await pilot.pause()

        app._apply_pi_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "apply failed" in footer
    assert notify_calls, "expected notify to be called with error"
    assert notify_calls[-1].get("severity") == "error"


@pytest.mark.asyncio
async def test_apply_pi_settings_error_surfaces(monkeypatch):
    """PiSettingsError must surface via notify + footer."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli._pi_settings as _settings
    import agent_toolkit_cli.pi_extension_lock as _lock
    import agent_toolkit_cli.pi_extension_ops as _ops

    notify_calls: list[Any] = []

    def fake_add_err(spec, *, scope, home=None, project=None):
        raise _settings.PiSettingsError("malformed JSON at /fake/settings.json")

    entry = MagicMock()
    entry.source_type = "npm"
    entry.source = "npm:bad-pkg"
    entry.ref = None
    entry.pi_extension_path = None

    def fake_read_lock(path):
        lf = MagicMock()
        lf.skills = {"bad-pkg": entry}
        return lf

    monkeypatch.setattr(_settings, "add_package", fake_add_err)
    monkeypatch.setattr(_lock, "read_lock", fake_read_lock)
    monkeypatch.setattr(_ops, "_global_entry", lambda slug: entry)
    monkeypatch.setattr("agent_toolkit_cli.pi_extension_paths.library_lock_path", lambda env=None: Path("/fake/lock"))

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        orig_notify = app.notify

        def spy_notify(*a, **k):
            notify_calls.append(k)
            return orig_notify(*a, **k)

        monkeypatch.setattr(app, "notify", spy_notify)
        app._active_asset_type = "pi-extension"
        grid = app.query_one("#pi-grid", PiGrid)
        grid.set_rows([_npm_row("bad-pkg", global_loaded=False)])
        grid.restore_pending({("global", "bad-pkg"): "link"})
        await pilot.pause()

        app._apply_pi_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "apply failed" in footer
    assert notify_calls, "expected notify to be called with error"
    assert notify_calls[-1].get("severity") == "error"


@pytest.mark.asyncio
async def test_apply_failure_preserves_pending(monkeypatch):
    """Latent bug (#349 spec §5): on failure _apply_pi_pending skipped
    clear_pending() but _refresh_pi_view()'s set_rows cleared anyway."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.pi_extension_install as _pi_install
    import agent_toolkit_cli.pi_extension_lock as _lock
    import agent_toolkit_cli.pi_extension_ops as _ops

    entry = MagicMock()
    fake_lock = MagicMock()
    fake_lock.skills = {"alpha": entry}
    monkeypatch.setattr(_lock, "read_lock", lambda path: fake_lock)
    monkeypatch.setattr(
        "agent_toolkit_cli.pi_extension_paths.library_lock_path",
        lambda env=None: Path("/fake/lock"),
    )

    def _boom(**kwargs: Any) -> None:
        raise _pi_install.InstallError("boom")

    monkeypatch.setattr(_ops, "install", _boom)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_pi_rows",
        lambda **kwargs: [_store_row("alpha")],
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_asset_type("pi-extension")
        await pilot.pause()
        grid = app.query_one("#pi-grid", PiGrid)
        grid._pending[("global", "alpha")] = "link"

        app.action_apply()
        await pilot.pause()

        assert grid.pending_entries() == {("global", "alpha"): "link"}, (
            "failed ops must stay queued for retry, like the other grids"
        )


@pytest.mark.asyncio
async def test_apply_multi_scope_footer_is_scope_tagged(monkeypatch):
    """Spanning-scope apply tags the footer summary (#349). Single-scope
    pending yields an empty tag, so only this fixture can catch a missing
    apply tag."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.pi_extension_lock as _lock
    import agent_toolkit_cli.pi_extension_ops as _ops

    entry = MagicMock()
    fake_lock = MagicMock()
    fake_lock.skills = {"alpha": entry}
    monkeypatch.setattr(_lock, "read_lock", lambda path: fake_lock)
    monkeypatch.setattr(
        "agent_toolkit_cli.pi_extension_paths.library_lock_path",
        lambda env=None: Path("/fake/lock"),
    )
    monkeypatch.setattr(_ops, "install", lambda **kwargs: None)
    monkeypatch.setattr(_ops, "uninstall", lambda **kwargs: None)
    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_pi_rows",
        lambda **kwargs: [_store_row("alpha")],
    )

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_asset_type("pi-extension")
        await pilot.pause()
        grid = app.query_one("#pi-grid", PiGrid)
        grid._pending[("global", "alpha")] = "link"
        grid._pending[("project", "alpha")] = "unlink"

        app.action_apply()
        await pilot.pause()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "applied: 2 ok, 0 failed (1 global, 1 project)" in footer


# ---------------------------------------------------------------------------
# Asset-type sidebar tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asset_type_sidebar_lists_both_asset_types():
    """The sidebar OptionList must include Skills and Pi Extensions options."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.query_one("#asset-types-list", OptionList)
        # Get option prompts
        prompts = [str(ol.get_option_at_index(i).prompt) for i in range(ol.option_count)]
        assert any("Skills" in p for p in prompts)
        assert any("Pi Extensions" in p for p in prompts)


@pytest.mark.asyncio
async def test_switch_to_pi_shows_pi_grid():
    """Switching to pi-extension asset type makes PiGrid visible and SkillGrid hidden."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_asset_type("pi-extension")
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        assert pi_grid.display is True
        assert skill_grid.display is False


@pytest.mark.asyncio
async def test_switch_to_skill_shows_skill_grid():
    """Starting on the skill asset type: SkillGrid is visible, PiGrid is not."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Default is skill; confirm it
        pi_grid = app.query_one("#pi-grid", PiGrid)
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        assert skill_grid.display is True
        assert pi_grid.display is False


@pytest.mark.asyncio
async def test_switch_pi_then_back_to_skill():
    """Can round-trip skill → pi-extension → skill."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_asset_type("pi-extension")
        await pilot.pause()
        app.action_asset_type("skill")
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        assert skill_grid.display is True
        assert pi_grid.display is False


@pytest.mark.asyncio
async def test_ctrl_s_routes_to_pi_apply_when_active(monkeypatch):
    """ctrl+s dispatches to _apply_pi_pending when pi-extension asset type is active."""
    from agent_toolkit_tui.app import TUIApp

    called: list[str] = []

    def fake_apply_pi(self):  # noqa: ANN001
        called.append("pi")

    def fake_apply_skill(self):  # noqa: ANN001
        called.append("skill")

    monkeypatch.setattr(TUIApp, "_apply_pi_pending", fake_apply_pi)
    monkeypatch.setattr(TUIApp, "_apply_skill_pending", fake_apply_skill)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_asset_type = "pi-extension"
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert "pi" in called
    assert "skill" not in called


@pytest.mark.asyncio
async def test_ctrl_s_routes_to_skill_apply_when_active(monkeypatch):
    """ctrl+s dispatches to _apply_skill_pending when skill asset type is active (default)."""
    from agent_toolkit_tui.app import TUIApp

    called: list[str] = []

    def fake_apply_pi(self):  # noqa: ANN001
        called.append("pi")

    def fake_apply_skill(self):  # noqa: ANN001
        called.append("skill")

    monkeypatch.setattr(TUIApp, "_apply_pi_pending", fake_apply_pi)
    monkeypatch.setattr(TUIApp, "_apply_skill_pending", fake_apply_skill)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Default asset type is skill
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert "skill" in called
    assert "pi" not in called

@pytest.mark.asyncio
async def test_project_install_global_loaded_row_is_non_interactive():
    """Project-scope unloaded cell with global-loaded marker cannot queue install."""

    class _A(App):
        def compose(self) -> ComposeResult:
            grid = PiGrid([_store_row("alpha", global_loaded=True, project_loaded=False)], id="g")
            grid.set_scope("project")
            yield grid

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

    assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_project_uninstall_global_loaded_row_still_queues_unlink():
    """Existing duplicate state can still be cleaned up from project scope."""

    class _A(App):
        def compose(self) -> ComposeResult:
            grid = PiGrid([_store_row("alpha", global_loaded=True, project_loaded=True)], id="g")
            grid.set_scope("project")
            yield grid

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", PiGrid)
        table = app.query_one("#pi-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

    assert g.pending_entries() == {("project", "alpha"): "unlink"}


def test_project_info_explains_global_loaded_install_block():
    grid = PiGrid([_store_row("alpha", global_loaded=True, project_loaded=False)])
    row = grid._rows[0]

    body = grid._info_body(row=row, scope="project")

    assert "Already loaded globally" in body
    assert "uninstall globally" in body
    assert "queue install" not in body

@pytest.mark.asyncio
async def test_apply_project_link_fails_when_global_loaded(monkeypatch):
    """Stale queued project link still fails through shared pi_extension_ops guard."""
    from agent_toolkit_tui.app import TUIApp
    import agent_toolkit_cli.pi_extension_install as _pi_install
    import agent_toolkit_cli.pi_extension_lock as _lock
    import agent_toolkit_cli.pi_extension_ops as _ops

    notify_calls: list[Any] = []

    entry = MagicMock()
    entry.source_type = "git"
    entry.source = "git@github.com:x/alpha"
    entry.ref = "main"
    entry.pi_extension_path = None

    def fake_read_lock(path):
        lf = MagicMock()
        lf.skills = {"alpha": entry}
        return lf

    def fake_global_plan(*, slug, scope, action, home=None, project=None):
        assert slug == "alpha"
        assert scope == "global"
        assert action == "install"
        return MagicMock(create=False)

    monkeypatch.setattr(_lock, "read_lock", fake_read_lock)
    monkeypatch.setattr(_ops, "_global_entry", lambda slug: entry)
    monkeypatch.setattr(_pi_install, "plan", fake_global_plan)
    monkeypatch.setattr("agent_toolkit_cli.pi_extension_paths.library_lock_path", lambda env=None: Path("/fake/lock"))

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        orig_notify = app.notify

        def spy_notify(*a, **k):
            notify_calls.append(k)
            return orig_notify(*a, **k)

        monkeypatch.setattr(app, "notify", spy_notify)
        app._active_asset_type = "pi-extension"
        grid = app.query_one("#pi-grid", PiGrid)
        grid.set_rows([_store_row("alpha", global_loaded=True, project_loaded=False)])
        grid.restore_pending({("project", "alpha"): "link"})
        await pilot.pause()

        app._apply_pi_pending()
        footer = str(app.query_one("#footer-pending", Static).render())

    assert "apply failed" in footer
    assert "already installed at global scope" in footer
    assert notify_calls
    assert notify_calls[-1].get("severity") == "error"
