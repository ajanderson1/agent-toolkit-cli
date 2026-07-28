"""Regression tests for SkillGrid's split info affordances (#479).

Header clicks explain columns; `i` always explains the selected skill.
"""
from __future__ import annotations

import pytest
from rich.text import Text
from textual.app import App
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_cli.skill_agents import get_standard_agents
from agent_toolkit_tui.screens.cell_info import CellInfoScreen
from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _row(slug: str, *, scope: str = "global") -> SkillRow:
    cells = {
        (agent, scope): SkillCell(linked=False, drift=False, skipped=False)
        for agent in INTERACTIVE_AGENTS
    }
    return SkillRow(
        slug=slug,
        source=f"x/{slug}",
        ref="main",
        state="clean",
        cells=cells,
    )


def _post_header(grid: SkillGrid, table: DataTable, index: int) -> None:
    grid.post_message(
        DataTable.HeaderSelected(
            table,
            column_key=list(table.columns)[index],
            column_index=index,
            label=Text(str(list(table.columns.values())[index].label)),
        )
    )


@pytest.mark.asyncio
async def test_only_column_info_headers_have_glyphs() -> None:
    """The asset and Source headers are passive; every column-info header is glyphed."""

    class _A(App[None]):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        labels = [
            str(column.label)
            for column in app.query_one("#skill-table", DataTable).columns.values()
        ]

        assert labels[0] == "Skill"
        assert labels[1] == f"Standard ({len(get_standard_agents())}) ⓘ"
        assert labels[2:6] == ["Claude ⓘ", "Pi ⓘ", "Hermes ⓘ", "Paperclip ⓘ"]
        assert labels[-2:] == ["State ⓘ", "Source"]


@pytest.mark.asyncio
async def test_click_standard_header_opens_column_info_modal() -> None:
    class _A(App[None]):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", SkillGrid)
        table = app.query_one("#skill-table", DataTable)
        _post_header(grid, table, 1)
        await pilot.pause()

        assert isinstance(app.screen, ColumnInfoModal)
        assert app.screen._info.title == "Standard — Skills"
        assert any(".agents/skills/<slug>/" in line for line in app.screen._info.lines)


@pytest.mark.asyncio
async def test_i_opens_identical_asset_info_from_standard_harness_and_state() -> None:
    class _A(App[None]):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#skill-table", DataTable)
        panels: list[tuple[str, str]] = []
        for column in (1, 2, len(INTERACTIVE_AGENTS) + 1):
            table.cursor_coordinate = Coordinate(row=0, column=column)
            table.focus()
            await pilot.press("i")
            await pilot.pause()
            assert isinstance(app.screen, CellInfoScreen)
            assert not isinstance(app.screen, ColumnInfoModal)
            panels.append((app.screen._title, app.screen._body_markup))
            await pilot.press("escape")
            await pilot.pause()

        assert panels[0] == panels[1] == panels[2]
        assert panels[0][0] == "alpha · Skill"


@pytest.mark.asyncio
async def test_column_key_for_index_resolves_every_explainable_header() -> None:
    class _A(App[None]):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", SkillGrid)
        count = len(INTERACTIVE_AGENTS)

        assert grid._column_key_for_index(0) is None
        for index, agent in enumerate(INTERACTIVE_AGENTS, start=1):
            assert grid._column_key_for_index(index) == agent
        assert grid._column_key_for_index(count + 1) == "state"
        assert grid._column_key_for_index(count + 2) is None


@pytest.mark.asyncio
async def test_click_state_header_opens_state_legend() -> None:
    class _A(App[None]):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", SkillGrid)
        table = app.query_one("#skill-table", DataTable)
        _post_header(grid, table, len(INTERACTIVE_AGENTS) + 1)
        await pilot.pause()

        assert isinstance(app.screen, ColumnInfoModal)
        assert app.screen._info.title == "State badges — Skills"
        assert any("unlisted" in line for line in app.screen._info.lines)


@pytest.mark.asyncio
@pytest.mark.parametrize("globally_linked", [False, True])
async def test_standard_header_marker_matches_selected_row(globally_linked: bool) -> None:
    cells = {
        (agent, scope): SkillCell(linked=False, drift=False, skipped=False)
        for agent in INTERACTIVE_AGENTS
        for scope in ("global", "project")
    }
    cells[("standard", "global")] = SkillCell(
        linked=globally_linked,
        drift=False,
        skipped=False,
    )
    row = SkillRow(
        slug="alpha",
        source="x/alpha",
        ref="main",
        state="library",
        cells=cells,
    )

    class _A(App[None]):
        def compose(self):
            grid = SkillGrid([row], id="g")
            grid.set_scope("project")
            yield grid

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", SkillGrid)
        table = app.query_one("#skill-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        _post_header(grid, table, 1)
        await pilot.pause()

        assert isinstance(app.screen, ColumnInfoModal)
        text = "\n".join(app.screen._info.lines)
        assert ("🌐" in text) is globally_linked
