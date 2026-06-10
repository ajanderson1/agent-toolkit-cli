"""Unit tests for ScopeToggle — paired-toggle widget for the TUI content header.

These tests exercise the widget in isolation (no app, no runner) to lock its
contract: it composes two labels, exposes set_active(scope), and dispatches
clicks to the app's action_scope action.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Label

from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets import ScopeToggle


class _Host(App):
    """Minimal host app so the widget can be mounted in a pilot."""

    def __init__(self) -> None:
        super().__init__()
        self.scope_calls: list[str] = []

    def compose(self) -> ComposeResult:
        yield ScopeToggle(active="project", id="scope-toggle")

    def action_scope(self, scope: str) -> None:
        self.scope_calls.append(scope)


@pytest.mark.asyncio
async def test_scope_toggle_renders_both_labels():
    """ScopeToggle composes one Label per scope value (project, global)."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        labels = list(app.query(ScopeToggle).first().query(Label))
        texts = {str(label.render()).strip() for label in labels}
        assert {"project", "global"}.issubset(texts)


@pytest.mark.asyncio
async def test_scope_toggle_set_active_marks_classes():
    """set_active(scope) flips the -active / -inactive classes on each label."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        toggle = app.query_one(ScopeToggle)

        toggle.set_active("global")
        await pilot.pause()
        project_label = toggle.query_one("#scope-toggle-project", Label)
        global_label = toggle.query_one("#scope-toggle-global", Label)
        assert "-active" in global_label.classes
        assert "-inactive" in project_label.classes
        assert "-active" not in project_label.classes
        assert "-inactive" not in global_label.classes


@pytest.mark.asyncio
async def test_scope_toggle_click_dispatches_action_scope():
    """Clicking a scope label calls app.action_scope with that scope name."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Click the inactive ('global') label directly.
        await pilot.click("#scope-toggle-global")
        await pilot.pause()
        assert app.scope_calls == ["global"]


@pytest.mark.asyncio
async def test_s_key_in_filter_does_not_toggle_scope():
    """On load the skills filter has focus; pressing `s` must insert literal
    text and NOT toggle scope (#320)."""
    from textual.widgets import Input

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        before = app._scope  # type: ignore[attr-defined]
        filter_input = app.query_one("#skill-filter", Input)
        assert app.focused is filter_input, "filter should have focus on load"
        await pilot.press("s")
        await pilot.pause()
        assert app._scope == before, "`s` must not toggle scope anymore"  # type: ignore[attr-defined]
        assert "s" in filter_input.value, "`s` should be inserted as filter text"


@pytest.mark.asyncio
async def test_s_key_with_table_focus_does_not_toggle_scope():
    """The discriminating case: with the skills TABLE focused (not the filter),
    `s` must STILL not toggle scope — proves the binding was removed, not just
    swallowed by the Input. This assertion is False on the old `s`-bound app
    and True after the rebind (#320)."""
    from textual.widgets import DataTable

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        before = app._scope  # type: ignore[attr-defined]
        app.query_one("#skill-table", DataTable).focus()
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        assert app._scope == before, "`s` must not toggle scope from the table either"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_ctrl_g_toggles_scope_even_with_filter_focus():
    """`ctrl+g` toggles scope even while the filter block has focus (#320)."""
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        before = app._scope  # type: ignore[attr-defined]
        await pilot.press("ctrl+g")
        await pilot.pause()
        assert app._scope != before, "`ctrl+g` must toggle scope"  # type: ignore[attr-defined]
        # And it flips back.
        await pilot.press("ctrl+g")
        await pilot.pause()
        assert app._scope == before  # type: ignore[attr-defined]


def test_scope_to_roots_project_mode_passes_home():
    """In project scope the TUI must pass Path.home() so build_skill_rows
    can populate (agent, 'global') cells for the indicator (#188)."""
    app = TUIApp()
    app._scope = "project"  # type: ignore[attr-defined]
    scope, home, project = app._scope_to_roots()  # type: ignore[attr-defined]
    assert scope == "project"
    assert home == Path.home(), f"expected Path.home(), got {home!r}"
    assert project == Path.cwd(), f"expected Path.cwd(), got {project!r}"


def test_scope_to_roots_global_mode_unchanged():
    app = TUIApp()
    app._scope = "global"  # type: ignore[attr-defined]
    scope, home, project = app._scope_to_roots()  # type: ignore[attr-defined]
    assert scope == "global"
    assert home == Path.home()
    assert project is None


@pytest.mark.asyncio
async def test_ctrl_g_on_pi_pane_refreshes_pi_not_skill():
    """Regression (#349): the old action_scope else-branch refreshed the
    HIDDEN skill grid when the pi pane was active, clearing its pending."""
    from agent_toolkit_tui.widgets import PiGrid, SkillGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        skill_grid._pending[("global", "claude", "alpha")] = "link"

        app.action_kind("pi-extension")
        await pilot.pause()
        await pilot.press("ctrl+g")
        await pilot.pause()

        assert skill_grid.pending_entries() == {
            ("global", "claude", "alpha"): "link"
        }, "hidden skill grid's pending must survive ctrl+g on the pi pane"


@pytest.mark.asyncio
async def test_pi_pane_shows_scope_toggle_and_cells_track_scope(monkeypatch):
    """The pi pane joins the scope toggle: widget visible, cell glyphs track
    the active scope with ctrl+g (the header carries no scope name, matching
    the other tabs, #349)."""
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable
    from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow

    def _row(slug):
        cell = PiCell(global_loaded=True, project_loaded=False, origin="store-owned")
        return PiExtensionRow(slug=slug, origin="store-owned",
                              source=f"git@github.com:x/{slug}",
                              global_cell=cell, project_cell=cell)

    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_pi_rows", lambda **kwargs: [_row("alpha")]
    )
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("pi-extension")
        await pilot.pause()
        assert app.query_one("#scope-toggle", ScopeToggle).display is True

        table = app.query_one("#pi-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert not any("global" in lbl.lower() or "project" in lbl.lower()
                       for lbl in labels)
        # App starts in project scope: alpha unloaded here, loaded globally.
        cell = str(table.get_cell_at(Coordinate(0, 1)))
        assert "☐" in cell and "🌐" in cell

        await pilot.press("ctrl+g")
        await pilot.pause()
        # Global scope: loaded glyph, no globe indicator.
        cell = str(table.get_cell_at(Coordinate(0, 1)))
        assert "✔" in cell and "🌐" not in cell


@pytest.mark.asyncio
async def test_pending_survives_scope_round_trip_pi(monkeypatch):
    """Queue pi ops → ctrl+g away and back → ops still queued AND still
    RENDERED (#349). The glyph assertion is load-bearing: restore_pending
    swallows rebuild failures in try/except, so dict equality alone cannot
    catch ops that were restored but never re-rendered."""
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable
    from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
    from agent_toolkit_tui.widgets import PiGrid

    def _row(slug):
        cell = PiCell(global_loaded=False, project_loaded=False, origin="store-owned")
        return PiExtensionRow(slug=slug, origin="store-owned",
                              source=f"git@github.com:x/{slug}",
                              global_cell=cell, project_cell=cell)

    monkeypatch.setattr(
        "agent_toolkit_tui.app.build_pi_rows",
        lambda **kwargs: [_row("alpha"), _row("beta")],
    )
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("pi-extension")
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        pi_grid._pending[("project", "alpha")] = "link"
        pi_grid._pending[("global", "beta")] = "unlink"

        await pilot.press("ctrl+g")
        await pilot.pause()
        await pilot.press("ctrl+g")
        await pilot.pause()

        assert pi_grid.pending_entries() == {
            ("project", "alpha"): "link",
            ("global", "beta"): "unlink",
        }
        # Back in project scope: row 0 (alpha) must RENDER its pending '+'.
        table = app.query_one("#pi-table", DataTable)
        assert "+" in str(table.get_cell_at(Coordinate(0, 1)))


@pytest.mark.asyncio
async def test_pending_survives_scope_round_trip_skill():
    """Same single mechanism covers the harness-keyed grids (#349)."""
    from agent_toolkit_tui.widgets import SkillGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()  # skill pane is active on load
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        skill_grid._pending[("project", "claude", "alpha")] = "link"

        await pilot.press("ctrl+g")
        await pilot.pause()
        assert skill_grid.pending_entries() == {
            ("project", "claude", "alpha"): "link"
        }, "pending must survive the toggle away"


@pytest.mark.asyncio
async def test_footer_pending_label_scope_tagged_when_spanning():
    from textual.widgets import Static
    from agent_toolkit_tui.widgets import PiGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("pi-extension")
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        pi_grid._pending[("project", "alpha")] = "link"
        pi_grid._pending[("global", "beta")] = "link"
        pi_grid._pending[("global", "gamma")] = "unlink"
        app._refresh_pending_label()
        label = str(app.query_one("#footer-pending", Static).render())
        assert "Pending: 3 (2 global, 1 project)" in label


@pytest.mark.asyncio
async def test_footer_pending_label_plain_when_single_scope():
    from textual.widgets import Static
    from agent_toolkit_tui.widgets import PiGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        pi_grid._pending[("global", "beta")] = "link"
        app._refresh_pending_label()
        label = str(app.query_one("#footer-pending", Static).render())
        assert "Pending: 1" in label
        assert "(" not in label.split("Pending: 1")[1][:2]


@pytest.mark.asyncio
async def test_diff_scope_tagged_when_spanning():
    """ctrl+d output attributes ops when they span scopes (#349)."""
    from textual.widgets import Static
    from agent_toolkit_tui.widgets import PiGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("pi-extension")
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        pi_grid._pending[("project", "alpha")] = "link"
        pi_grid._pending[("global", "beta")] = "unlink"
        app.action_diff()
        label = str(app.query_one("#footer-pending", Static).render())
        assert "diff: 1 would-link, 1 would-unlink (1 global, 1 project)" in label


@pytest.mark.asyncio
async def test_revert_clears_both_scopes_and_is_scope_tagged():
    """ctrl+z is the one destructive surface that can consume invisible
    other-scope ops — it clears the whole grid dict and says so (#349)."""
    from textual.widgets import Static
    from agent_toolkit_tui.widgets import PiGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_kind("pi-extension")
        await pilot.pause()
        pi_grid = app.query_one("#pi-grid", PiGrid)
        pi_grid._pending[("project", "alpha")] = "link"
        pi_grid._pending[("global", "beta")] = "unlink"
        pi_grid._pending[("global", "gamma")] = "link"
        app.action_revert()
        await pilot.pause()
        assert pi_grid.pending_entries() == {}
        label = str(app.query_one("#footer-pending", Static).render())
        assert "reverted: 3 pending cleared (2 global, 1 project)" in label


@pytest.mark.asyncio
async def test_ctrl_r_still_clears_pending():
    """Explicit refresh keeps its clearing semantics (#349 out-of-scope guard)."""
    from agent_toolkit_tui.widgets import SkillGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        skill_grid._pending[("project", "claude", "alpha")] = "link"
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert skill_grid.pending_entries() == {}
