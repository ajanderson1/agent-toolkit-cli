"""Pilot tests for the InstructionGrid widget and the instruction TUI flow.

Covers (widget-level + app-level):

Widget-level:
1.  columns renders correctly (Instruction + Standard (N) + interactive_harnesses() + Source)
2.  row count
3.  toggle unlinked cell queues 'link'
4.  toggle linked cell queues 'unlink'
5.  toggle twice clears pending
6.  PendingChanged message carries count
7.  toggle_column (action_a) queues all in column
8.  set_scope clears pending
9.  conflict cell is non-toggleable (no-op)
10. standard column is non-toggleable (no-op)

App-level:
11. sidebar lists six active asset types with instruction first
12. switching to instruction shows InstructionGrid, hides others
13. ctrl+s routes to _apply_instruction_pending when instruction active
Real lockless save, retry, source-chain protection and rendered evidence live in
 test_instruction_lockless.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.events import Resize
from textual.geometry import Size
from textual.widgets import DataTable, OptionList, Static

from agent_toolkit_tui.instruction_state import (
    interactive_harnesses,
    InstructionCell,
    InstructionRow,
)
from agent_toolkit_tui.widgets.instruction_grid import InstructionGrid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unlinked_row(slug: str = "AGENTS.md", *, scope: str = "global") -> InstructionRow:
    """Row with all interactive_harnesses() unlinked at the given scope."""
    cells = {
        (h, scope): InstructionCell(linked=False, conflict=False)
        for h in interactive_harnesses()
    }
    return InstructionRow(
        slug=slug,
        source="AGENTS.md",
        canonical_exists=True,
        cells=cells,
    )


def _linked_row(slug: str = "AGENTS.md", *, scope: str = "global") -> InstructionRow:
    """Row with all interactive_harnesses() linked at the given scope."""
    cells = {
        (h, scope): InstructionCell(linked=True, conflict=False)
        for h in interactive_harnesses()
    }
    return InstructionRow(
        slug=slug,
        source="AGENTS.md",
        canonical_exists=True,
        cells=cells,
    )


def _conflict_row(slug: str = "AGENTS.md", *, scope: str = "global") -> InstructionRow:
    """Row with all interactive_harnesses() in conflict state."""
    cells = {
        (h, scope): InstructionCell(linked=False, conflict=True)
        for h in interactive_harnesses()
    }
    return InstructionRow(
        slug=slug,
        source="AGENTS.md",
        canonical_exists=True,
        cells=cells,
    )


# ---------------------------------------------------------------------------
# Widget-level tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_instruction_grid_resize_fits_source_text_when_room_permits():
    """InstructionGrid sizes Source to its displayed text."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        table = app.query_one("#instruction-table", DataTable)
        event = Resize(Size(140, 24), Size(140, 24))

        g.on_resize(event)

        source = list(table.columns.values())[-1]
        assert source.width == 10


@pytest.mark.asyncio
async def test_instruction_grid_mounts_with_correct_columns():
    """Grid must show Instruction + Standard (N) + interactive_harnesses() + Source."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#instruction-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        # Slug + standard + N harness cols + Source
        assert len(labels) == len(interactive_harnesses(scope="global")) + 3
        assert "Instruction" in labels
        assert "Instruction ⓘ" not in labels
        assert not any("INSTRUCTION" in lbl for lbl in labels)
        assert any(label.startswith("Standard (") for label in labels)
        assert not any("Claude Code" in label for label in labels)
        assert not any("Gemini CLI" in label for label in labels)
        assert any("Source" in lbl for lbl in labels)


@pytest.mark.asyncio
async def test_instruction_grid_row_count():
    """Row count equals the number of rows passed in."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        assert g.row_count == 1
        assert g.row_slugs == ["AGENTS.md"]


@pytest.mark.asyncio
async def test_toggle_unlinked_cell_queues_link():
    """Space on an unlinked harness cell queues 'link'."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        # Column layout: [0]=slug, [1]=standard, [2]=first harness, ...
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        pending = g.pending_entries()
        first_harness = interactive_harnesses()[0]
        assert pending.get(("global", first_harness, "AGENTS.md")) == "link"


@pytest.mark.asyncio
async def test_toggle_linked_cell_queues_unlink():
    """Space on a linked cell queues 'unlink'."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_linked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        pending = g.pending_entries()
        first_harness = interactive_harnesses()[0]
        assert pending.get(("global", first_harness, "AGENTS.md")) == "unlink"


@pytest.mark.asyncio
async def test_toggle_twice_clears_pending():
    """Toggling the same cell twice returns to empty pending."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.press("space")
        assert g.pending_entries() == {}


def test_pending_changed_message_carries_count():
    """PendingChanged(count) stores the count."""
    msg = InstructionGrid.PendingChanged(5)
    assert msg.count == 5


def test_standard_glyph_is_neutral_when_canonical_exists():
    """Existing canonical AGENTS.md is informational, not installed status."""
    row = InstructionRow(
        slug="AGENTS.md",
        source="AGENTS.md",
        canonical_exists=True,
        cells={},
    )
    grid = InstructionGrid([row])

    glyph = grid._standard_glyph(row)  # type: ignore[attr-defined]

    assert "✔" not in glyph
    assert "green" not in glyph
    assert "AGENTS.md" in glyph or "std" in glyph


def test_standard_glyph_reports_missing_when_canonical_absent():
    """Missing canonical AGENTS.md remains visibly actionable/error-like."""
    row = InstructionRow(
        slug="AGENTS.md",
        source="AGENTS.md",
        canonical_exists=False,
        cells={},
    )
    grid = InstructionGrid([row])

    glyph = grid._standard_glyph(row)  # type: ignore[attr-defined]

    assert "missing" in glyph or "✘" in glyph
    assert "red" in glyph


@pytest.mark.asyncio
async def test_pending_changed_fires_on_toggle():
    """PendingChanged is posted when a cell is toggled."""
    received: list[int] = []

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

        def on_instruction_grid_pending_changed(
            self, event: InstructionGrid.PendingChanged
        ) -> None:
            received.append(event.count)

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

    assert 1 in received


@pytest.mark.asyncio
async def test_toggle_column_queues_all_in_column():
    """'a' key on a harness column toggles all rows in that column."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid(
                [_unlinked_row("AGENTS.md")],
                id="g",
            )

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("a")
        pending = g.pending_entries()
        first_harness = interactive_harnesses()[0]
        assert pending.get(("global", first_harness, "AGENTS.md")) == "link"


@pytest.mark.asyncio
async def test_set_scope_clears_pending():
    """set_scope clears any pending entries."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() != {}
        g.set_scope("project")
        assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_conflict_cell_is_not_toggled():
    """Space on a conflict cell is a no-op (never queues a toggle)."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_conflict_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        # No toggle queued for conflict cell
        assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_standard_column_is_not_toggled():
    """Space on the standard (column 1) is a no-op."""

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        # Column 1 = standard
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=1)
        table.focus()
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {}


@pytest.mark.asyncio
async def test_asset_info_shows_canonical_path_from_harness_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """`i` stays asset-level while retaining the canonical instruction path."""
    home = tmp_path / "home"
    home.mkdir()
    agent_toolkit_dir = home / ".agent-toolkit"
    agent_toolkit_dir.mkdir()
    canonical = agent_toolkit_dir / "AGENTS.md"
    canonical.write_text("# AGENTS\n")

    monkeypatch.setattr(
        "agent_toolkit_cli.instructions_paths.library_root",
        lambda: agent_toolkit_dir / "instructions",
    )
    monkeypatch.setenv("HOME", str(home))

    row = InstructionRow(
        slug="AGENTS.md",
        source="AGENTS.md",
        canonical_exists=True,
        cells={
            ("claude-code", "global"): InstructionCell(
                linked=False, conflict=False,
            ),
        },
    )

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([row], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("global")
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=2)
        table.focus()
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()

        from agent_toolkit_tui.screens.cell_info import CellInfoScreen

        assert isinstance(app.screen, CellInfoScreen)
        body = app.screen._body_markup
        assert str(canonical) in body
        assert str(home / ".claude" / "CLAUDE.md") not in body
        assert "State (global): canonical present" in body


@pytest.mark.asyncio
async def test_slug_info_at_project_scope_does_not_crash():
    """`i` on the slug column at project scope opens the info modal.

    Regression: the project-scope branch resolved the canonical path with
    project_canonical_agents_md(None), which raises (it requires a real Path).
    It must use the project root (cwd) instead.
    """

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row(scope="project")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        g = app.query_one("#g", InstructionGrid)
        g.set_scope("project")
        table = app.query_one("#instruction-table", DataTable)
        # Column 0 = slug (INSTRUCTION).
        table.cursor_coordinate = table.cursor_coordinate.__class__(row=0, column=0)
        table.focus()
        await pilot.pause()
        # Must not raise; a CellInfoScreen should be pushed onto the stack
        # (it would have raised TypeError before the fix).
        await pilot.press("i")
        await pilot.pause()
        from agent_toolkit_tui.screens.cell_info import CellInfoScreen

        screen = app.screen
        assert isinstance(screen, CellInfoScreen)
        # The slug-column body names the canonical AGENTS.md at the project root.
        assert "AGENTS.md" in screen._body_markup
        assert str(Path.cwd()) in screen._body_markup

@pytest.mark.asyncio
async def test_instruction_i_opens_asset_info_from_harness_column():
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    from agent_toolkit_tui.screens.cell_info import CellInfoScreen

    class _A(App):
        def compose(self) -> ComposeResult:
            yield InstructionGrid([_unlinked_row()], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#instruction-table", DataTable)
        table.cursor_coordinate = Coordinate(row=0, column=2)  # claude-code
        table.focus()
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, CellInfoScreen)
        assert app.screen._title == "AGENTS.md · Instruction"
        assert "Source: AGENTS.md" in app.screen._body_markup
        assert "State (global): canonical present" in app.screen._body_markup


# ---------------------------------------------------------------------------
# App-level tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_asset_type_sidebar_lists_instruction_first():
    """Sidebar lists only six enabled asset types in the established order."""
    from agent_toolkit_tui.app import TUIApp

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        ol = app.query_one("#asset-types-list", OptionList)
        assert ol.option_count == 6
        options = [ol.get_option_at_index(i) for i in range(ol.option_count)]
        assert all(not option.disabled for option in options)
        assert [option.id for option in options] == [
            "asset-type-instruction",
            "asset-type-command",
            "asset-type-skill",
            "asset-type-agent",
            "asset-type-mcp",
            "asset-type-pi-extension",
        ]


@pytest.mark.asyncio
async def test_switch_to_instruction_shows_instruction_grid():
    """Switching to instruction asset type makes InstructionGrid visible, others hidden."""
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.agent_grid import AgentGrid
    from agent_toolkit_tui.widgets.pi_grid import PiGrid
    from agent_toolkit_tui.widgets.skill_grid import SkillGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_asset_type("instruction")
        await pilot.pause()
        instruction_grid = app.query_one("#instruction-grid", InstructionGrid)
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        pi_grid = app.query_one("#pi-grid", PiGrid)
        agent_grid = app.query_one("#agent-grid", AgentGrid)
        assert instruction_grid.display is True
        assert skill_grid.display is False
        assert pi_grid.display is False
        assert agent_grid.display is False


@pytest.mark.asyncio
async def test_switch_to_instruction_then_back_to_skill():
    """Can round-trip skill → instruction → skill."""
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.skill_grid import SkillGrid

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_asset_type("instruction")
        await pilot.pause()
        app.action_asset_type("skill")
        await pilot.pause()
        instruction_grid = app.query_one("#instruction-grid", InstructionGrid)
        skill_grid = app.query_one("#skill-grid", SkillGrid)
        assert skill_grid.display is True
        assert instruction_grid.display is False


@pytest.mark.asyncio
async def test_ctrl_s_routes_to_instruction_apply_when_active(monkeypatch):
    """ctrl+s dispatches to _apply_instruction_pending when instruction asset type is active."""
    from agent_toolkit_tui.app import TUIApp

    called: list[str] = []

    def fake_apply_instruction(self) -> None:  # noqa: ANN001
        called.append("instruction")

    def fake_apply_skill(self) -> None:  # noqa: ANN001
        called.append("skill")

    def fake_apply_agent(self) -> None:  # noqa: ANN001
        called.append("agent")

    monkeypatch.setattr(TUIApp, "_apply_instruction_pending", fake_apply_instruction)
    monkeypatch.setattr(TUIApp, "_apply_skill_pending", fake_apply_skill)
    monkeypatch.setattr(TUIApp, "_apply_agent_pending", fake_apply_agent)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._active_asset_type = "instruction"
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert "instruction" in called
    assert "skill" not in called
    assert "agent" not in called
