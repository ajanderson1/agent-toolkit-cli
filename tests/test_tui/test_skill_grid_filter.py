"""Tests for the TUI fuzzy-filter search box (#249).

The v1 TUI had a filter box at the top: focused on open, typing narrowed the
list, Down/Tab dropped focus into the main pane. This file locks that behaviour
back in for the v2 skill-only grid.

Matching is case-insensitive substring on the slug — the same logic v1 used.
Algorithm changes are explicitly out of scope for the issue.
"""
from __future__ import annotations

import pytest
from textual.widgets import DataTable, Input

from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _row(slug: str, *, scope: str = "global",
         linked: tuple[str, ...] = ()) -> SkillRow:
    cells = {
        (a, scope): SkillCell(linked=(a in linked), drift=False, skipped=False)
        for a in INTERACTIVE_AGENTS
    }
    return SkillRow(
        slug=slug, source=f"x/{slug}", ref="main", state="clean", cells=cells,
    )


def _slugs(grid: SkillGrid) -> list[str]:
    return [r.slug for r in grid._visible_rows()]


# ----- Phase 1: filtered view ----------------------------------------------

@pytest.mark.asyncio
async def test_visible_rows_substring():
    grid = SkillGrid([_row("alpha"), _row("beta"), _row("gamma")],
                     id="skill-grid")
    app = TUIApp()
    async with app.run_test() as pilot:
        # Replace the app's grid rows so we control the data set.
        app.query_one("#skill-grid", SkillGrid).set_rows(
            [_row("alpha"), _row("beta"), _row("gamma")]
        )
        await pilot.pause()
        g = app.query_one("#skill-grid", SkillGrid)
        g.set_filter("a")
        await pilot.pause()
        # "a" appears in alpha, beta, gamma — all three.
        assert _slugs(g) == ["alpha", "beta", "gamma"]
        g.set_filter("be")
        await pilot.pause()
        assert _slugs(g) == ["beta"]
        g.set_filter("")
        await pilot.pause()
        assert _slugs(g) == ["alpha", "beta", "gamma"]


@pytest.mark.asyncio
async def test_visible_rows_case_insensitive():
    app = TUIApp()
    async with app.run_test() as pilot:
        g = app.query_one("#skill-grid", SkillGrid)
        g.set_rows([_row("alpha"), _row("beta"), _row("gamma")])
        await pilot.pause()
        g.set_filter("BETA")
        await pilot.pause()
        assert _slugs(g) == ["beta"]


@pytest.mark.asyncio
async def test_row_count_unaffected_by_filter():
    app = TUIApp()
    async with app.run_test() as pilot:
        g = app.query_one("#skill-grid", SkillGrid)
        g.set_rows([_row("alpha"), _row("beta"), _row("gamma")])
        await pilot.pause()
        g.set_filter("be")
        await pilot.pause()
        # Full count stays 3 even though only one row is visible.
        assert g.row_count == 3
        assert len(_slugs(g)) == 1


# ----- Phase 2: input widget + wiring --------------------------------------

@pytest.mark.asyncio
async def test_filter_box_renders():
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        box = app.query_one("#skill-filter", Input)
        assert isinstance(box, Input)


@pytest.mark.asyncio
async def test_typing_narrows_rows():
    app = TUIApp()
    async with app.run_test() as pilot:
        g = app.query_one("#skill-grid", SkillGrid)
        g.set_rows([_row("alpha"), _row("beta"), _row("gamma")])
        await pilot.pause()
        app.query_one("#skill-filter", Input).focus()
        await pilot.pause()
        await pilot.press("b", "e")
        await pilot.pause()
        assert _slugs(g) == ["beta"]


@pytest.mark.asyncio
async def test_toggle_after_filter_targets_visible_row():
    """Filter to one slug, move into the table, space — pending key is that slug.

    Guards the cursor-index → visible-row remap: with a filter active the
    cursor row 0 must resolve to the *visible* row, not self._rows[0].
    """
    app = TUIApp()
    async with app.run_test() as pilot:
        app._scope = "global"
        g = app.query_one("#skill-grid", SkillGrid)
        g.set_scope("global")
        g.set_rows([_row("alpha"), _row("beta"), _row("gamma")])
        await pilot.pause()
        g.set_filter("beta")
        await pilot.pause()
        # Cursor onto the (only visible) row's claude-code cell and toggle.
        g.cursor_to_cell(row_slug="beta", agent_name="claude-code")
        await pilot.pause()
        g.action_toggle_cell()
        await pilot.pause()
        pending = g.pending_entries()
        assert list(pending.keys()) == [("global", "claude-code", "beta")]


@pytest.mark.asyncio
async def test_all_ignores_filter():
    """'All/None' (a) toggles every row, regardless of the active filter."""
    app = TUIApp()
    async with app.run_test() as pilot:
        app._scope = "global"
        g = app.query_one("#skill-grid", SkillGrid)
        g.set_scope("global")
        g.set_rows([_row("alpha"), _row("beta"), _row("gamma")])
        await pilot.pause()
        g.set_filter("beta")  # hides alpha + gamma
        await pilot.pause()
        # Cursor onto the claude-code column, press 'a'.
        g.cursor_to_cell(row_slug="beta", agent_name="claude-code")
        await pilot.pause()
        g.action_toggle_column()
        await pilot.pause()
        pending_slugs = {slug for (_s, _a, slug) in g.pending_entries()}
        # All three slugs get a pending link, not just the visible one.
        assert pending_slugs == {"alpha", "beta", "gamma"}


# ----- Phase 3: focus + escape ---------------------------------------------

@pytest.mark.asyncio
async def test_focus_starts_in_filter():
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.focused is not None
        assert app.focused.id == "skill-filter"


@pytest.mark.asyncio
async def test_down_moves_focus_to_table():
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#skill-filter", Input).focus()
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert app.focused is not None
        assert app.focused.id == "skill-table"


@pytest.mark.asyncio
async def test_tab_moves_focus_to_table():
    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.query_one("#skill-filter", Input).focus()
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        assert app.focused is not None
        assert app.focused.id == "skill-table"
