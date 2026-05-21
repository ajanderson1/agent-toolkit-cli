"""Pilot tests for SkillGrid's column-info wiring."""
from __future__ import annotations

import pytest

from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _row(slug: str, *, scope: str = "global") -> SkillRow:
    cells = {(a, scope): SkillCell(linked=False, drift=False, skipped=False)
             for a in INTERACTIVE_AGENTS}
    return SkillRow(
        slug=slug, source=f"x/{slug}", ref="main",
        state="clean", cells=cells,
    )


@pytest.mark.asyncio
async def test_universal_column_label_has_info_glyph():
    """The universal column label includes the ⓘ glyph; others do not."""
    from textual.app import App
    from textual.widgets import DataTable

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        # Layout: slug | description | universal | claude-code | pi | state | source
        assert labels[1] == "description", f"description label missing: {labels[1]!r}"
        assert "ⓘ" in labels[2], f"universal label missing glyph: {labels[2]!r}"
        assert "ⓘ" not in labels[3], f"claude-code label has glyph: {labels[3]!r}"
        assert "ⓘ" not in labels[4], f"pi label has glyph: {labels[4]!r}"
        assert labels[-1] == "source", f"source label missing: {labels[-1]!r}"


@pytest.mark.asyncio
async def test_press_i_on_universal_column_opens_modal():
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="alpha", agent_name="universal")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert any(isinstance(s, ColumnInfoModal) for s in a.screen_stack), \
            "ColumnInfoModal not pushed"


@pytest.mark.asyncio
async def test_press_i_on_claude_code_column_is_noop():
    """No info registered for claude-code → pressing i does nothing."""
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="alpha", agent_name="claude-code")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert not any(isinstance(s, ColumnInfoModal) for s in a.screen_stack)


@pytest.mark.asyncio
async def test_press_i_on_slug_column_is_noop():
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=0)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert not any(isinstance(s, ColumnInfoModal) for s in a.screen_stack)


@pytest.mark.asyncio
async def test_column_key_for_index_resolves_state():
    from textual.app import App
    from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        state_col = 1 + len(INTERACTIVE_AGENTS)
        assert g._column_key_for_index(0) is None
        assert g._column_key_for_index(state_col) == "state"
        for i, agent in enumerate(INTERACTIVE_AGENTS, start=1):
            assert g._column_key_for_index(i) == agent
        assert g._column_key_for_index(state_col + 1) is None
