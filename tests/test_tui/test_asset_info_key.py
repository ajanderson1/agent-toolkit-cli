"""`i` always explains the selected asset, never the selected column (#479)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.agent_state import (
    interactive_harnesses as _agent_harnesses,
    AgentCell,
    AgentRow,
)
from agent_toolkit_tui.command_state import (
    interactive_harnesses as _command_harnesses,
    CommandCell,
    CommandRow,
)
from agent_toolkit_tui.instruction_state import (
    interactive_harnesses as _instruction_harnesses,
    InstructionCell,
    InstructionRow,
)
from agent_toolkit_tui.mcp_state import McpCell, McpRow
from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
from agent_toolkit_tui.screens.cell_info import CellInfoScreen
from agent_toolkit_tui.skill_state import interactive_agents, SkillCell, SkillRow
from agent_toolkit_tui.widgets.agent_grid import AgentGrid
from agent_toolkit_tui.widgets.command_grid import CommandGrid
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid
from agent_toolkit_tui.widgets.mcp_grid import McpGrid
from agent_toolkit_tui.widgets.pi_grid import PiGrid
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


@dataclass(frozen=True)
class _Case:
    name: str
    table_id: str
    make_grid: Callable[[], object]
    expected_title: str


def _skill_grid(description: str = "A test skill.") -> SkillGrid:
    cells = {
        (harness, "global"): SkillCell(linked=False, drift=False, skipped=False)
        for harness in interactive_agents()
    }
    return SkillGrid(
        [
            SkillRow(
                slug="demo",
                source="owner/repo",
                ref="main",
                state="clean",
                cells=cells,
                description=description,
            )
        ],
        id="grid",
    )


def _instruction_grid() -> InstructionGrid:
    cells = {
        (harness, "global"): InstructionCell(linked=False, conflict=False)
        for harness in _instruction_harnesses()
    }
    return InstructionGrid(
        [InstructionRow(slug="AGENTS.md", source="AGENTS.md", canonical_exists=True, cells=cells)],
        id="grid",
    )


def _agent_grid() -> AgentGrid:
    cells = {
        (harness, "global"): AgentCell(linked=False)
        for harness in _agent_harnesses("global")
    }
    return AgentGrid(
        [AgentRow(slug="demo", source="owner/repo", ref="main", cells=cells)],
        id="grid",
    )


def _mcp_grid() -> McpGrid:
    cells = {
        (harness, "global"): McpCell(linked=False)
        for harness in ("claude-code", "codex", "opencode", "pi")
    }
    return McpGrid(
        [McpRow(slug="demo", source="npx", pin="1.2.3", state="installed", cells=cells)],
        id="grid",
    )


def _command_grid() -> CommandGrid:
    cells = {
        (harness, "global"): CommandCell(linked=False)
        for harness in _command_harnesses()
    }
    return CommandGrid(
        [CommandRow(slug="demo", source="owner/repo", ref="main", cells=cells)],
        id="grid",
    )


def _pi_grid() -> PiGrid:
    cell = PiCell(global_loaded=False, project_loaded=False, origin="store-owned")
    return PiGrid(
        [
            PiExtensionRow(
                slug="demo",
                origin="store-owned",
                source="owner/repo",
                global_cell=cell,
                project_cell=cell,
            )
        ],
        id="grid",
    )


CASES = (
    _Case("skill", "skill-table", _skill_grid, "demo · Skill"),
    _Case("instruction", "instruction-table", _instruction_grid, "AGENTS.md · Instruction"),
    _Case("agent", "agent-table", _agent_grid, "demo · Agent"),
    _Case("mcp", "mcp-table", _mcp_grid, "demo · MCP"),
    _Case("command", "command-table", _command_grid, "demo · Command"),
    _Case("pi-extension", "pi-table", _pi_grid, "demo · Pi Extension"),
)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
async def test_i_opens_an_asset_panel_for_every_grid(case: _Case) -> None:
    grid = case.make_grid()

    class _A(App[None]):
        def compose(self) -> ComposeResult:
            yield grid  # type: ignore[misc]

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one(f"#{case.table_id}", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(app.screen, CellInfoScreen)
        assert app.screen._title == case.expected_title
        body = app.screen._body_markup
        assert "Source:" in body
        assert "Ref:" in body
        assert "State (global):" in body


@pytest.mark.asyncio
async def test_i_shows_the_identical_skill_panel_from_slug_standard_and_state() -> None:
    grid = _skill_grid()

    class _A(App[None]):
        def compose(self) -> ComposeResult:
            yield grid

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#skill-table", DataTable)
        state_column = len(interactive_agents()) + 1
        panels: list[tuple[str, str]] = []

        for column in (0, 1, state_column):
            table.cursor_coordinate = Coordinate(row=0, column=column)
            table.focus()
            await pilot.press("i")
            await pilot.pause()
            assert isinstance(app.screen, CellInfoScreen)
            panels.append((app.screen._title, app.screen._body_markup))
            await pilot.press("escape")
            await pilot.pause()

        assert panels[0] == panels[1] == panels[2]


@pytest.mark.asyncio
async def test_app_i_opens_the_command_asset_panel() -> None:
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("command")
        await pilot.pause()
        grid = app.query_one("#command-grid", CommandGrid)
        grid.set_rows([CommandRow(slug="demo", source="owner/repo", ref="main", cells={})])
        table = app.query_one("#command-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)

        app.action_info_pass()
        await pilot.pause()

        assert isinstance(app.screen, CellInfoScreen)
        assert app.screen._title == "demo · Command"


@pytest.mark.asyncio
async def test_i_says_when_a_skill_has_no_description() -> None:
    grid = _skill_grid(description="")

    class _A(App[None]):
        def compose(self) -> ComposeResult:
            yield grid

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#skill-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=0)
        table.focus()
        await pilot.press("i")
        await pilot.pause()

        assert isinstance(app.screen, CellInfoScreen)
        assert "No description in SKILL.md." in app.screen._body_markup


@pytest.mark.asyncio
async def test_i_with_zero_visible_rows_is_a_noop() -> None:
    grid = _skill_grid()

    class _A(App[None]):
        def compose(self) -> ComposeResult:
            yield grid

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid.set_filter("no-match")
        await pilot.pause()
        table = app.query_one("#skill-table", DataTable)
        assert table.row_count == 0
        table.focus()
        await pilot.press("i")
        await pilot.pause()

        assert not isinstance(app.screen, CellInfoScreen)
