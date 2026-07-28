"""Standard column on the instruction grid (#351).

Standard read-only column leads; Claude + Gemini follow (implicitly
non-standard — single-line headers). The long tail is CLI-only (post-demo AJ
decision). Header click owns registry dispatch; `i` remains asset-level.
"""
from __future__ import annotations

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from agent_toolkit_tui.composition import instructions_nonstandard_main
from agent_toolkit_tui.instruction_state import InstructionCell, InstructionRow
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid


def _full_row(slug: str = "AGENTS.md", *, scope: str = "global") -> InstructionRow:
    cells = {
        (h, scope): InstructionCell(linked=False, conflict=False)
        for h in instructions_nonstandard_main()
    }
    return InstructionRow(
        slug=slug, source="AGENTS.md", canonical_exists=True, cells=cells,
    )


class _GridApp(App):
    def compose(self) -> ComposeResult:
        yield InstructionGrid([_full_row()], id="g")


def _post_standard_header(grid: InstructionGrid, table: DataTable) -> None:
    grid.post_message(
        DataTable.HeaderSelected(
            table,
            column_key=list(table.columns)[1],
            column_index=1,
            label=Text(str(list(table.columns.values())[1].label)),
        )
    )


@pytest.mark.asyncio
async def test_columns_are_standard_plus_noncovered_main():
    app = _GridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#instruction-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        # slug + Standard (N) + Claude + Gemini + source
        assert labels[0] == "Instruction"
        assert labels[1].startswith("Standard (")
        assert any("Claude ⓘ" == l for l in labels)
        assert any("Gemini ⓘ" == l for l in labels)
        assert not any("claude-code" in l or "gemini-cli" in l for l in labels)
        assert not any("Claude Code" in l or "Gemini CLI" in l for l in labels)
        # No pseudo-column, no group tags, single-line labels only.
        assert not any("… +" in l or "STANDARD" in l or "NON-STD" in l
                       or "\n" in l for l in labels), labels
        assert len(labels) == len(instructions_nonstandard_main()) + 3


@pytest.mark.asyncio
async def test_click_standard_header_opens_registry_modal():
    from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal

    app = _GridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        _post_standard_header(grid, table)
        await pilot.pause()
        assert isinstance(app.screen, ColumnInfoModal)
        body = str(app.screen.query_one("#column-info-body").render())
        assert "Covered harnesses (39)" in body
        assert "Adal" in body  # a native reader, enumerated exhaustively
