"""Standard column on the instruction grid (#351).

Standard read-only column leads; claude-code + gemini-cli follow (implicitly
non-standard — single-line headers). The long tail is CLI-only (post-demo AJ
decision). The `i` registry dispatch (ported from skill_grid, replacing the
old inline column-1 branch) is pinned here.
"""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
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


@pytest.mark.asyncio
async def test_columns_are_standard_plus_noncovered_main():
    app = _GridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#instruction-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        # slug + standard + claude-code + gemini-cli + source
        assert "standard" in labels[1]
        assert any("CLAUDE.md" in l for l in labels)
        assert any("GEMINI.md" in l for l in labels)
        # No pseudo-column, no group tags, single-line labels only.
        assert not any("… +" in l or "STANDARD" in l or "NON-STD" in l
                       or "\n" in l for l in labels), labels
        assert len(labels) == len(instructions_nonstandard_main()) + 3


@pytest.mark.asyncio
async def test_press_i_on_standard_column_opens_registry_modal():
    """The inline coord.column==1 branch is replaced by the registry path:
    `i` on the standard column opens ColumnInfoModal with the exhaustive
    native list (kind-aware via context)."""
    from agent_toolkit_tui.widgets.column_info_modal import ColumnInfoModal

    app = _GridApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, ColumnInfoModal), \
            "ColumnInfoModal not pushed for the standard column"
        body = str(app.screen.query_one("#column-info-body").render())
        assert "instructions" in body and "(39)" in body
        assert "adal" in body  # a native reader, enumerated exhaustively
