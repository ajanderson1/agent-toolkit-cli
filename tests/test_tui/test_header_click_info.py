"""Header clicks open authored column info; passive headers stay passive (#479)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from agent_toolkit_tui.agent_state import (
    interactive_harnesses as _agent_harnesses,
    AgentCell,
    AgentRow,
)
from agent_toolkit_tui.column_info import get_column_info
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
from agent_toolkit_tui.skill_state import interactive_agents, SkillCell, SkillRow
from agent_toolkit_tui.widgets.agent_grid import AgentGrid
from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal
from agent_toolkit_tui.widgets.command_grid import CommandGrid
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid
from agent_toolkit_tui.widgets.mcp_grid import McpGrid
from agent_toolkit_tui.widgets.pi_grid import PiGrid
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


@dataclass(frozen=True)
class _Case:
    name: str
    asset_type: str
    scope: str
    table_id: str
    make_grid: Callable[[], object]
    expected_keys: tuple[str, ...]


def _skill_grid() -> SkillGrid:
    cells = {
        (harness, "global"): SkillCell(linked=False, drift=False, skipped=False)
        for harness in interactive_agents()
    }
    return SkillGrid(
        [SkillRow(slug="demo", source="owner/repo", ref="main", state="clean", cells=cells)],
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


def _mcp_global_grid() -> McpGrid:
    cells = {
        (harness, "global"): McpCell(linked=False)
        for harness in ("claude-code", "codex", "opencode", "pi")
    }
    return McpGrid(
        [McpRow(slug="demo", source="npx", pin=None, state="installed", cells=cells)],
        id="grid",
    )


def _mcp_project_grid() -> McpGrid:
    cells = {
        (harness, "project"): McpCell(linked=False)
        for harness in ("standard", "codex", "opencode")
    }
    grid = McpGrid(
        [McpRow(slug="demo", source="npx", pin=None, state="installed", cells=cells)],
        id="grid",
    )
    grid.set_scope("project")
    return grid


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
    _Case(
        "skills",
        "skill",
        "global",
        "skill-table",
        _skill_grid,
        ("standard", "claude-code", "hermes-agent", "paperclip", "pi", "state"),
    ),
    _Case(
        "instructions",
        "instruction",
        "global",
        "instruction-table",
        _instruction_grid,
        ("standard", "claude-code", "gemini-cli"),
    ),
    _Case(
        "agents",
        "agent",
        "global",
        "agent-table",
        _agent_grid,
        ("standard", "gemini-cli", "opencode", "pi", "state"),
    ),
    _Case(
        "mcps-global",
        "mcp",
        "global",
        "mcp-table",
        _mcp_global_grid,
        ("claude-code", "codex", "opencode", "pi", "state"),
    ),
    _Case(
        "mcps-project",
        "mcp",
        "project",
        "mcp-table",
        _mcp_project_grid,
        ("standard", "codex", "opencode", "state"),
    ),
    _Case(
        "commands",
        "command",
        "global",
        "command-table",
        _command_grid,
        ("claude-code", "codex", "gemini-cli", "pi", "state"),
    ),
    _Case(
        "pi-extensions",
        "pi-extension",
        "global",
        "pi-table",
        _pi_grid,
        ("pi", "origin"),
    ),
)


def _post_header(grid: object, table: DataTable, index: int) -> None:
    grid.post_message(  # type: ignore[attr-defined]
        DataTable.HeaderSelected(
            table,
            column_key=list(table.columns)[index],
            column_index=index,
            label=Text(str(list(table.columns.values())[index].label)),
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
async def test_clicking_each_glyphed_header_opens_its_column_info(case: _Case) -> None:
    grid = case.make_grid()

    class _A(App[None]):
        def compose(self) -> ComposeResult:
            yield grid  # type: ignore[misc]

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one(f"#{case.table_id}", DataTable)
        labels = [str(column.label) for column in table.columns.values()]
        glyphed_indices = [index for index, label in enumerate(labels) if "ⓘ" in label]

        # The glyph is honest: every glyph maps to one of the authored pairs.
        keys = [grid._column_key_for_index(index) for index in glyphed_indices]  # type: ignore[attr-defined]
        assert keys == list(case.expected_keys)

        for index, key in zip(glyphed_indices, case.expected_keys, strict=True):
            _post_header(grid, table, index)
            await pilot.pause()
            assert isinstance(app.screen, ColumnInfoModal)
            expected = get_column_info(
                key,
                asset_type=case.asset_type,
                context={"scope": case.scope},
            )
            assert app.screen._info.title == expected.title
            await pilot.press("escape")
            await pilot.pause()

        # Asset-slug and Source headers are intentionally glyph-free and passive.
        for index, label in enumerate(labels):
            if "ⓘ" in label:
                continue
            _post_header(grid, table, index)
            await pilot.pause()
            assert not isinstance(app.screen, ColumnInfoModal)
