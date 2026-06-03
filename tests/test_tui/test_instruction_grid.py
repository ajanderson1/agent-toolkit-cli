"""Tests for InstructionGrid widget — mirrors test_agent_grid.py pattern."""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from agent_toolkit_tui.instruction_state import (
    INTERACTIVE_HARNESSES,
    InstructionCell,
    InstructionRow,
)
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _linked_row(scope: str = "global") -> InstructionRow:
    """Row with both interactive harnesses linked."""
    return InstructionRow(
        slug="AGENTS.md",
        scope=scope,
        general_linked=True,
        cells={
            h: InstructionCell(applicable=True, linked=True)
            for h in INTERACTIVE_HARNESSES
        },
    )


def _unlinked_row(scope: str = "global") -> InstructionRow:
    """Row with both interactive harnesses unlinked."""
    return InstructionRow(
        slug="AGENTS.md",
        scope=scope,
        general_linked=True,
        cells={
            h: InstructionCell(applicable=True, linked=False)
            for h in INTERACTIVE_HARNESSES
        },
    )


def _not_applicable_row(scope: str = "global") -> InstructionRow:
    """Row where cells are not applicable."""
    return InstructionRow(
        slug="AGENTS.md",
        scope=scope,
        general_linked=False,
        cells={
            h: InstructionCell(applicable=False, linked=False)
            for h in INTERACTIVE_HARNESSES
        },
    )


# ---------------------------------------------------------------------------
# Widget-level tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_instruction_grid_columns():
    """Grid must show INSTRUCTION, Claude Code, Gemini CLI, and Source columns."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#instruction-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert any("INSTRUCTION" in lbl for lbl in labels)
        assert any("Claude Code" in lbl for lbl in labels)
        assert any("Gemini CLI" in lbl for lbl in labels)


@pytest.mark.asyncio
async def test_instruction_grid_row_count():
    """Row count equals the number of rows passed in."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid(
                [_unlinked_row("global"), _unlinked_row("project")],
                id="g",
            )

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        assert g.row_count == 2


@pytest.mark.asyncio
async def test_toggle_unlinked_cell_queues_link():
    """Space on a claude-code unlinked cell queues 'link'."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row("global")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        # Column 1 = first INTERACTIVE_HARNESSES entry (claude-code)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        pending = g.pending_entries()
        assert pending.get(("global", "claude-code", "AGENTS.md")) == "link"


@pytest.mark.asyncio
async def test_toggle_linked_cell_queues_unlink():
    """Space on a linked cell queues 'unlink'."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_linked_row("global")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        pending = g.pending_entries()
        assert pending.get(("global", "claude-code", "AGENTS.md")) == "unlink"


@pytest.mark.asyncio
async def test_toggle_twice_clears_pending():
    """Toggling the same cell twice returns to empty pending."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row("global")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.press("space")
        assert g.pending_entries() == {}


def test_pending_changed_message_carries_count():
    """PendingChanged(count) stores the count."""
    msg = InstructionGrid.PendingChanged(3)
    assert msg.count == 3


@pytest.mark.asyncio
async def test_pending_changed_fires_on_toggle():
    """PendingChanged is posted when a cell is toggled."""
    received: list[int] = []

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row("global")], id="g")

        def on_instruction_grid_pending_changed(
            self, event: InstructionGrid.PendingChanged
        ) -> None:
            received.append(event.count)

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

    assert 1 in received


@pytest.mark.asyncio
async def test_not_applicable_cell_is_not_toggleable():
    """A not-applicable cell (applicable=False) cannot be toggled."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_not_applicable_row("global")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_set_rows_clears_pending():
    """set_rows() clears any pending entries."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row("global")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() != {}
        g.set_rows([_unlinked_row("project")])
        assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_clear_pending_works():
    """clear_pending() removes all pending entries."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row("global")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        g.clear_pending()
        assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_restore_pending_works():
    """restore_pending() restores previously saved pending entries."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row("global")], id="g")

    app = _A()
    saved = {("global", "claude-code", "AGENTS.md"): "link"}
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.restore_pending(saved)
        assert g.pending_entries() == saved
