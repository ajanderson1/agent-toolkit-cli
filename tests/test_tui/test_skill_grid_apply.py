"""Pilot tests for the interactive SkillGrid."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _row(slug: str, *, scope="global",
         linked: tuple[str, ...] = (),
         skipped: tuple[str, ...] = ()) -> SkillRow:
    cells = {}
    for a in INTERACTIVE_AGENTS:
        cells[(a, scope)] = SkillCell(
            linked=(a in linked), drift=False, skipped=(a in skipped),
        )
    return SkillRow(
        slug=slug, source=f"x/{slug}", ref="main",
        state="clean", cells=cells,
    )


@pytest.mark.asyncio
async def test_grid_mounts_with_columns():
    from textual.app import App
    class _A(App):
        def compose(self):
            yield SkillGrid([_row("j")], id="g")
    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        assert g.row_count == 1
        assert g.row_slugs == ["j"]


@pytest.mark.asyncio
async def test_toggle_cell_queues_link():
    from textual.app import App
    class _A(App):
        def compose(self):
            yield SkillGrid([_row("j", linked=())], id="g")
    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="j", agent_name="claude-code")
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {("global", "claude-code", "j"): "link"}


@pytest.mark.asyncio
async def test_toggle_universal_project_linked_queues_unlink():
    """#232: a checked Universal cell at project scope must queue an unlink.

    Previously a guard early-returned for (universal, project, linked), so the
    cell could never be un-toggled. The engine (post-#237) handles the unlink.
    """
    from textual.app import App
    class _A(App):
        def compose(self):
            yield SkillGrid([_row("j", scope="project", linked=("universal",))], id="g")
    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        g.cursor_to_cell(row_slug="j", agent_name="universal")
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {("project", "universal", "j"): "unlink"}


@pytest.mark.asyncio
async def test_toggle_universal_project_unlinked_queues_link():
    """#232 inverse: an unchecked Universal cell at project scope queues a link."""
    from textual.app import App
    class _A(App):
        def compose(self):
            yield SkillGrid([_row("j", scope="project", linked=())], id="g")
    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        g.cursor_to_cell(row_slug="j", agent_name="universal")
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {("project", "universal", "j"): "link"}


@pytest.mark.asyncio
async def test_toggle_twice_clears_pending():
    from textual.app import App
    class _A(App):
        def compose(self):
            yield SkillGrid([_row("j")], id="g")
    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="j", agent_name="claude-code")
        await pilot.pause()
        await pilot.press("space")
        await pilot.press("space")
        assert g.pending_entries() == {}
