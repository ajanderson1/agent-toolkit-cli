"""Pilot tests for the CellInfoScreen modal."""
from __future__ import annotations

import pytest

from agent_toolkit_tui.screens.cell_info import CellInfoScreen
from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _row(
    slug: str,
    *,
    scope: str = "global",
    linked: tuple[str, ...] = (),
    drifted: tuple[str, ...] = (),
    skipped: tuple[str, ...] = (),
    description: str = "",
) -> SkillRow:
    cells = {}
    for a in INTERACTIVE_AGENTS:
        cells[(a, scope)] = SkillCell(
            linked=(a in linked),
            drift=(a in drifted),
            skipped=(a in skipped),
        )
    return SkillRow(
        slug=slug,
        source=f"x/{slug}",
        ref="main",
        state="clean",
        cells=cells,
        description=description,
    )


@pytest.mark.asyncio
async def test_modal_renders_title_and_body():
    from textual.app import App
    pushed: list[CellInfoScreen] = []

    class _A(App):
        def on_mount(self):
            screen = CellInfoScreen(
                title="demo · claude-code @ global",
                body_markup="Linked.\nPath: /tmp/x",
            )
            pushed.append(screen)
            self.push_screen(screen)

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        assert pushed
        text = pushed[0].query_one("#cell-info-body").content
        # Rich Text or str — coerce both.
        rendered = str(text)
        assert "Linked." in rendered
        assert "/tmp/x" in rendered


@pytest.mark.asyncio
async def test_modal_dismisses_on_escape():
    from textual.app import App

    class _A(App):
        def on_mount(self):
            self.push_screen(CellInfoScreen(title="t", body_markup="b"))

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(a.screen, CellInfoScreen)


@pytest.mark.asyncio
async def test_info_on_drift_cell_shows_doctor_command():
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("journal", drifted=("claude-code",))], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="journal", agent_name="claude-code")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen)
        body = str(a.screen.query_one("#cell-info-body").content)
        assert "skill doctor journal -g" in body
        assert "drift" in body.lower()


@pytest.mark.asyncio
async def test_info_on_unlinked_cell_explains_space():
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("journal")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="journal", agent_name="claude-code")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen)
        body = str(a.screen.query_one("#cell-info-body").content)
        assert "space" in body.lower()


@pytest.mark.asyncio
async def test_info_on_slug_column_shows_source():
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("journal")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        from textual.coordinate import Coordinate
        from textual.widgets import DataTable
        t = g.query_one("#skill-table", DataTable)
        t.cursor_coordinate = Coordinate(row=0, column=0)  # slug col
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen)
        body = str(a.screen.query_one("#cell-info-body").content)
        assert "x/journal" in body  # the source string from _row


@pytest.mark.asyncio
async def test_info_on_slug_column_includes_description_when_present():
    """A row with a SKILL.md description surfaces it under the slug-cell info body."""
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("journal", description="An atomic-note journal skill.")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        t = g.query_one("#skill-table", DataTable)
        t.cursor_coordinate = Coordinate(row=0, column=0)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen)
        body = str(a.screen.query_one("#cell-info-body").content)
        assert "Description" in body
        assert "An atomic-note journal skill." in body


@pytest.mark.asyncio
async def test_info_on_slug_column_omits_description_when_empty():
    """No `Description:` label appears when the row has no description string."""
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("journal", description="")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        t = g.query_one("#skill-table", DataTable)
        t.cursor_coordinate = Coordinate(row=0, column=0)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen)
        body = str(a.screen.query_one("#cell-info-body").content)
        assert "Description" not in body


@pytest.mark.asyncio
async def test_info_on_slug_column_library_state_renders_em_dash():
    """A row in the 'library' state shows `State:  —` (em dash), not the literal word (#212)."""
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    # Build a row with state='library' — _row() defaults to 'clean', so override.
    row = _row("journal")
    row.state = "library"

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        t = g.query_one("#skill-table", DataTable)
        t.cursor_coordinate = Coordinate(row=0, column=0)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen)
        body = str(a.screen.query_one("#cell-info-body").content)
        assert "State:  —" in body, f"expected em-dash for library state, got: {body!r}"
        assert "State:  library" not in body, (
            f"slug-cell modal should not print literal 'library', got: {body!r}"
        )


@pytest.mark.asyncio
async def test_info_on_slug_column_non_library_state_still_renders_word():
    """A non-library state still shows the literal state value (e.g. 'clean')."""
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable

    row = _row("journal")  # state defaults to 'clean'

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        t = g.query_one("#skill-table", DataTable)
        t.cursor_coordinate = Coordinate(row=0, column=0)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(a.screen, CellInfoScreen)
        body = str(a.screen.query_one("#cell-info-body").content)
        assert "State:  clean" in body, f"non-library state should render literal: {body!r}"
