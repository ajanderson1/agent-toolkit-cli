"""Pilot tests for SkillGrid's column-info wiring.

`i` routes via `_column_key_for_index`:
  - Standard / State (have a registered ColumnInfo) → ColumnInfoModal
  - Agent columns (Claude Code, Pi) / slug / source → CellInfoScreen
"""
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
async def test_columns_have_info_glyph_except_source():
    """Every column whose cells expose an info panel gets ⓘ; Source is passive (#212)."""
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
        # Layout (#351): SKILL | Standard | Claude Code | Pi | … +N | State |
        # Source — single-line labels; Standard leads, the rest is implicitly
        # non-standard.
        assert labels[0] == "SKILL ⓘ", f"slug label: {labels[0]!r}"
        assert labels[1] == "Standard ⓘ", f"standard label: {labels[1]!r}"
        assert labels[2] == "Claude Code ⓘ", f"claude-code label: {labels[2]!r}"
        assert labels[3] == "Pi ⓘ", f"pi label: {labels[3]!r}"
        assert labels[4].startswith("… +"), f"pseudo label: {labels[4]!r}"
        assert labels[-2] == "State ⓘ", f"state label: {labels[-2]!r}"
        assert labels[-1] == "Source", f"source label: {labels[-1]!r}"
        assert "ⓘ" not in labels[-1], f"source must not have glyph: {labels[-1]!r}"


@pytest.mark.asyncio
async def test_press_i_on_universal_column_opens_column_info_modal():
    """i on universal column opens ColumnInfoModal (registered column info)."""
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="alpha", agent_name="standard")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, ColumnInfoModal), \
            "ColumnInfoModal not pushed for universal column"


@pytest.mark.asyncio
async def test_press_i_on_claude_code_column_opens_cell_info():
    """i on agent (non-info-registered) columns opens CellInfoScreen with cell state."""
    from textual.app import App

    from agent_toolkit_tui.screens.cell_info import CellInfoScreen

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
        assert isinstance(a.screen, CellInfoScreen), \
            "CellInfoScreen not pushed for claude-code column"


@pytest.mark.asyncio
async def test_press_i_on_slug_column_opens_cell_info():
    """i on the slug column opens CellInfoScreen (not ColumnInfoModal)."""
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    from agent_toolkit_tui.screens.cell_info import CellInfoScreen

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=0)
        table.focus()  # filter Input is focused on open (#249); table needs focus to receive `i`
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen), \
            "CellInfoScreen not pushed for slug column"
        assert not any(isinstance(s, ColumnInfoModal) for s in a.screen_stack)


@pytest.mark.asyncio
async def test_column_key_for_index_resolves_state():
    """Layout (#351): [0]=SKILL, [1..N]=agents, [N+1]=longtail, [N+2]=State, [N+3]=Source."""
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
        assert g._column_key_for_index(0) is None       # SKILL
        for i, agent in enumerate(INTERACTIVE_AGENTS, start=1):
            assert g._column_key_for_index(i) == agent
        assert g._column_key_for_index(n + 1) == "longtail"
        assert g._column_key_for_index(n + 2) == "state"
        assert g._column_key_for_index(n + 3) is None  # Source


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
        state_col = len(INTERACTIVE_AGENTS) + 2  # +1 = longtail pseudo (#351)
        table.cursor_coordinate = Coordinate(row=0, column=state_col)
        table.focus()  # filter Input is focused on open (#249); table needs focus to receive `i`
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
        assert labels[0] == "SKILL ⓘ", f"slug header: {labels[0]!r}"


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
        state_col = len(INTERACTIVE_AGENTS) + 2  # +1 = longtail pseudo (#351)
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
        from agent_toolkit_tui.composition import skills_longtail
        labels = [str(c.label) for c in table.columns.values()]
        assert labels == [
            "SKILL ⓘ",
            "Standard ⓘ",
            "Claude Code ⓘ",
            "Pi ⓘ",
            f"… +{len(skills_longtail())} ⓘ",
            "State ⓘ",
            "Source",
        ], f"unexpected header row: {labels!r}"


@pytest.mark.asyncio
async def test_universal_modal_omits_global_marker_when_not_globally_linked():
    """In project scope, opening the Standard column info on a row whose global
    cell is NOT linked produces a modal without the 🌐 marker paragraph (#212)."""
    from textual.app import App

    from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow

    # Project-scope row with global cells populated but NOT linked.
    cells = {}
    for a in INTERACTIVE_AGENTS:
        cells[(a, "project")] = SkillCell(linked=False, drift=False, skipped=False)
        cells[(a, "global")] = SkillCell(linked=False, drift=False, skipped=False)
    row = SkillRow(slug="alpha", source="x/alpha", ref="main", state="library", cells=cells)

    class _A(App):
        def compose(self):
            grid = SkillGrid([row], id="g")
            grid.set_scope("project")
            yield grid

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="alpha", agent_name="standard")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, ColumnInfoModal)
        text = "\n".join(a.screen._info.lines)
        assert "🌐" not in text, f"unexpected 🌐 in modal: {a.screen._info.lines}"


@pytest.mark.asyncio
async def test_universal_modal_keeps_global_marker_when_globally_linked():
    """In project scope, opening the Standard column info on a row whose global
    cell IS linked still includes the 🌐 marker paragraph."""
    from textual.app import App

    from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow

    cells = {}
    for a in INTERACTIVE_AGENTS:
        cells[(a, "project")] = SkillCell(linked=False, drift=False, skipped=False)
        cells[(a, "global")] = SkillCell(linked=False, drift=False, skipped=False)
    # The universal global cell is linked — caller has the skill globally installed.
    cells[("standard", "global")] = SkillCell(linked=True, drift=False, skipped=False)
    row = SkillRow(slug="alpha", source="x/alpha", ref="main", state="library", cells=cells)

    class _A(App):
        def compose(self):
            grid = SkillGrid([row], id="g")
            grid.set_scope("project")
            yield grid

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="alpha", agent_name="standard")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, ColumnInfoModal)
        text = "\n".join(a.screen._info.lines)
        assert "🌐" in text, f"expected 🌐 in modal: {a.screen._info.lines}"
