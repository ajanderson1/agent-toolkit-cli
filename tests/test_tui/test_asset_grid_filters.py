from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input

from agent_toolkit_tui.agent_state import (
    INTERACTIVE_HARNESSES as AGENT_HARNESSES,
    AgentCell,
    AgentRow,
)
from agent_toolkit_tui.command_state import (
    INTERACTIVE_HARNESSES as COMMAND_HARNESSES,
    CommandCell,
    CommandRow,
)
from agent_toolkit_tui.instruction_state import (
    INTERACTIVE_HARNESSES as INSTRUCTION_HARNESSES,
    InstructionCell,
    InstructionRow,
)
from agent_toolkit_tui.mcp_state import McpCell, McpRow
from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
from agent_toolkit_tui.widgets.agent_grid import AgentGrid
from agent_toolkit_tui.widgets.command_grid import CommandGrid
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid
from agent_toolkit_tui.widgets.mcp_grid import McpGrid
from agent_toolkit_tui.widgets.pi_grid import PiGrid


def _slugs(table: DataTable) -> list[str]:
    return [str(table.get_row_at(i)[0]) for i in range(table.row_count)]


def _agent_row(slug: str, *, linked: bool = False) -> AgentRow:
    return AgentRow(
        slug=slug,
        source="owner/repo",
        ref="main",
        cells={(AGENT_HARNESSES[0], "global"): AgentCell(linked=linked)},
    )


class AgentGridApp(App[None]):
    def compose(self) -> ComposeResult:
        yield AgentGrid(
            [
                _agent_row("alpha"),
                _agent_row("beta"),
                _agent_row("gamma"),
            ],
            id="agent-grid",
        )


@pytest.mark.asyncio
async def test_agent_filter_matches_slug_case_insensitively():
    app = AgentGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#agent-grid", AgentGrid)
        table = app.query_one("#agent-table", DataTable)

        grid.set_filter("BETA")
        await pilot.pause()

        assert _slugs(table) == ["beta"]
        assert grid.row_count == 3


@pytest.mark.asyncio
async def test_agent_filter_typing_narrows_rows():
    app = AgentGridApp()
    async with app.run_test() as pilot:
        app.query_one("#agent-filter", Input).focus()
        await pilot.press("b", "e")

        table = app.query_one("#agent-table", DataTable)
        assert _slugs(table) == ["beta"]


@pytest.mark.asyncio
async def test_agent_filter_focus_handoff_keys():
    app = AgentGridApp()
    async with app.run_test() as pilot:
        app.query_one("#agent-filter", Input).focus()
        await pilot.press("down")
        assert app.focused is not None
        assert app.focused.id == "agent-table"

        app.query_one("#agent-filter", Input).focus()
        await pilot.press("tab")
        assert app.focused is not None
        assert app.focused.id == "agent-table"

        app.query_one("#agent-filter", Input).focus()
        await pilot.press("enter")
        assert app.focused is not None
        assert app.focused.id == "agent-table"


@pytest.mark.asyncio
async def test_agent_toggle_after_filter_targets_visible_row():
    app = AgentGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#agent-grid", AgentGrid)
        table = app.query_one("#agent-table", DataTable)
        grid.set_filter("beta")
        await pilot.pause()

        table.cursor_coordinate = Coordinate(row=table.cursor_coordinate.row, column=1)
        table.focus()
        await pilot.press("space")

        assert list(grid.pending_entries()) == [("global", AGENT_HARNESSES[0], "beta")]


@pytest.mark.asyncio
async def test_agent_zero_match_row_actions_noop():
    app = AgentGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#agent-grid", AgentGrid)
        table = app.query_one("#agent-table", DataTable)
        grid.set_filter("zzz")
        await pilot.pause()

        assert table.row_count == 0
        await pilot.press("space")
        await pilot.press("i")
        assert grid.pending_entries() == {}


@pytest.mark.asyncio
async def test_agent_bulk_action_ignores_filter():
    app = AgentGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#agent-grid", AgentGrid)
        table = app.query_one("#agent-table", DataTable)
        grid.set_filter("beta")
        await pilot.pause()

        table.cursor_coordinate = Coordinate(row=table.cursor_coordinate.row, column=1)
        table.focus()
        await pilot.press("a")

        pending_slugs = {key[2] for key in grid.pending_entries()}
        assert pending_slugs == {"alpha", "beta", "gamma"}


def _instruction_row(slug: str) -> InstructionRow:
    return InstructionRow(
        slug=slug,
        source=slug,
        canonical_exists=True,
        cells={
            (harness, "global"): InstructionCell(linked=False, conflict=False)
            for harness in INSTRUCTION_HARNESSES
        },
    )


class InstructionGridApp(App[None]):
    def compose(self) -> ComposeResult:
        yield InstructionGrid(
            [_instruction_row("AGENTS.md"), _instruction_row("GEMINI.md")],
            id="instruction-grid",
        )


@pytest.mark.asyncio
async def test_instruction_filter_smoke():
    app = InstructionGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#instruction-grid", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        grid.set_filter("gem")
        await pilot.pause()

        assert _slugs(table) == ["GEMINI.md"]
        assert grid.row_count == 2


def _command_row(slug: str) -> CommandRow:
    return CommandRow(
        slug=slug,
        source="owner/repo",
        ref="main",
        cells={(COMMAND_HARNESSES[0], "global"): CommandCell(linked=False)},
    )


class CommandGridApp(App[None]):
    def compose(self) -> ComposeResult:
        yield CommandGrid([_command_row("alpha"), _command_row("beta")], id="command-grid")


@pytest.mark.asyncio
async def test_command_filter_smoke():
    app = CommandGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#command-grid", CommandGrid)
        table = app.query_one("#command-table", DataTable)
        grid.set_filter("bet")
        await pilot.pause()

        assert _slugs(table) == ["beta"]
        assert grid.row_count == 2


def _pi_row(slug: str) -> PiExtensionRow:
    cell = PiCell(global_loaded=False, project_loaded=False, origin="store-owned")
    return PiExtensionRow(
        slug=slug,
        origin="store-owned",
        source=f"git@github.com:x/{slug}",
        global_cell=cell,
        project_cell=cell,
    )


class PiGridApp(App[None]):
    def compose(self) -> ComposeResult:
        yield PiGrid([_pi_row("alpha"), _pi_row("beta")], id="pi-grid")


@pytest.mark.asyncio
async def test_pi_filter_smoke():
    app = PiGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#pi-grid", PiGrid)
        table = app.query_one("#pi-table", DataTable)
        grid.set_filter("bet")
        await pilot.pause()

        assert _slugs(table) == ["beta"]
        assert grid.row_count == 2


def _mcp_row(slug: str) -> McpRow:
    return McpRow(
        slug=slug,
        source="npx",
        pin=None,
        state="installed",
        cells={("standard", "project"): McpCell(linked=False)},
    )


class McpGridApp(App[None]):
    def compose(self) -> ComposeResult:
        yield McpGrid([_mcp_row("alpha"), _mcp_row("beta")], id="mcp-grid")


@pytest.mark.asyncio
async def test_mcp_filter_smoke():
    app = McpGridApp()
    async with app.run_test() as pilot:
        grid = app.query_one("#mcp-grid", McpGrid)
        table = app.query_one("#mcp-table", DataTable)
        grid.set_filter("bet")
        await pilot.pause()

        assert _slugs(table) == ["beta"]
        assert grid.row_count == 2
