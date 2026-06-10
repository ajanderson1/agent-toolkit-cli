"""#351 must not touch the agents and pi-extensions grids.

The agents kind has no standard projection today (standard-agent is
synthetic, mechanism="none") and pi-extensions has no standard concept —
neither grid gets group tags, a pseudo-column, or a two-line header.
"""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from agent_toolkit_tui.agent_state import AgentCell, AgentRow
from agent_toolkit_tui.pi_extension_state import PiCell, PiExtensionRow
from agent_toolkit_tui.widgets.agent_grid import AgentGrid
from agent_toolkit_tui.widgets.pi_grid import PiGrid


def _agent_row(slug: str = "demo") -> AgentRow:
    return AgentRow(
        slug=slug, source=f"ajanderson1/{slug}", ref="main",
        cells={("claude-code", "global"): AgentCell(linked=True)},
    )


def _pi_row(slug: str = "demo") -> PiExtensionRow:
    cell = PiCell(global_loaded=True, project_loaded=False, origin="store-owned")
    return PiExtensionRow(
        slug=slug, origin="store-owned", source=f"git@github.com:x/{slug}",
        global_cell=cell, project_cell=cell,
    )


def _grouped_markers(labels: list[str]) -> list[str]:
    return [l for l in labels
            if "STANDARD" in l or "NON-STD" in l or "… +" in l or "\n" in l]


@pytest.mark.asyncio
async def test_agent_grid_columns_unchanged():
    class _A(App):
        def compose(self) -> ComposeResult:
            yield AgentGrid([_agent_row()], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#agent-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert not _grouped_markers(labels), \
            f"agent grid must be untouched by #351: {labels!r}"
        assert table.header_height == 1


@pytest.mark.asyncio
async def test_pi_grid_columns_unchanged():
    class _A(App):
        def compose(self) -> ComposeResult:
            yield PiGrid([_pi_row()], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#pi-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert not _grouped_markers(labels), \
            f"pi grid must be untouched by #351: {labels!r}"
        assert table.header_height == 1
