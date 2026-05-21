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
    """The universal column label is 'Universal ⓘ'; agent columns have no glyph."""
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
        # Layout: SKILL | Description | Universal ⓘ | Claude Code | Pi | State ⓘ | Source
        assert labels[1] == "Description", f"description label: {labels[1]!r}"
        assert labels[2] == "Universal ⓘ", f"universal label: {labels[2]!r}"
        assert "ⓘ" not in labels[3], f"claude-code label has glyph: {labels[3]!r}"
        assert "ⓘ" not in labels[4], f"pi label has glyph: {labels[4]!r}"
        assert labels[-1] == "Source", f"source label: {labels[-1]!r}"


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
    """Layout: [0]=SKILL, [1]=Description, [2..N+1]=agents, [N+2]=State, [N+3]=Source."""
    from textual.app import App
    from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        n = len(INTERACTIVE_AGENTS)
        state_col = n + 2
        source_col = n + 3
        assert g._column_key_for_index(0) is None       # SKILL
        assert g._column_key_for_index(1) is None       # Description
        for i, agent in enumerate(INTERACTIVE_AGENTS, start=2):
            assert g._column_key_for_index(i) == agent
        assert g._column_key_for_index(state_col) == "state"
        assert g._column_key_for_index(source_col) is None  # Source


@pytest.mark.asyncio
async def test_press_i_on_state_column_opens_modal():
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable
    from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        state_col = len(INTERACTIVE_AGENTS) + 2
        table.cursor_coordinate = Coordinate(row=0, column=state_col)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert any(isinstance(s, ColumnInfoModal) for s in a.screen_stack), \
            "ColumnInfoModal not pushed when pressing i on state column"


@pytest.mark.asyncio
async def test_slug_header_is_uppercase():
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
        assert labels[0] == "SKILL", f"slug header: {labels[0]!r}"


@pytest.mark.asyncio
async def test_state_header_is_capitalised_with_glyph():
    from textual.app import App
    from textual.widgets import DataTable
    from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        state_col = len(INTERACTIVE_AGENTS) + 2
        assert labels[state_col] == "State ⓘ", f"state header: {labels[state_col]!r}"


@pytest.mark.asyncio
async def test_full_header_row():
    """Header row matches spec exactly."""
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
        assert labels == [
            "SKILL", "Description", "Universal ⓘ", "Claude Code", "Pi",
            "State ⓘ", "Source",
        ], f"unexpected header row: {labels!r}"
