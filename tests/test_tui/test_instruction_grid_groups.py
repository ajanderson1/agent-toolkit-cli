"""Instructions grid renders only selected, actionable harness columns."""
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
        for h in instructions_nonstandard_main(scope=scope)
    }
    return InstructionRow(
        slug=slug, source="AGENTS.md", canonical_exists=True, cells=cells,
    )


class _GridApp(App):
    def compose(self) -> ComposeResult:
        yield InstructionGrid([_full_row()], id="g")


@pytest.mark.asyncio
async def test_columns_are_selected_actionable_harnesses_without_standard():
    app = _GridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#instruction-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert labels[0] == "Instruction"
        assert labels[-1] == "Source"
        assert any("Claude ⓘ" == label for label in labels)
        assert any("Gemini ⓘ" == label for label in labels)
        assert not any(label.startswith("Standard (") for label in labels)
        assert not any("… +" in label or "STANDARD" in label or "NON-STD" in label
                       or "\n" in label for label in labels), labels
        assert len(labels) == len(instructions_nonstandard_main(scope="global")) + 2


@pytest.mark.asyncio
async def test_click_harness_header_opens_pointer_info():
    from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal

    app = _GridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        grid = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        grid.post_message(
            DataTable.HeaderSelected(
                table,
                column_key=list(table.columns)[1],
                column_index=1,
                label=Text(str(list(table.columns.values())[1].label)),
            )
        )
        await pilot.pause()
        assert isinstance(app.screen, ColumnInfoModal)
        body = str(app.screen.query_one("#column-info-body").render())
        assert "Reads `CLAUDE.md`" in body
