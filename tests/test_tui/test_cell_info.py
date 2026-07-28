"""Pilot tests for the shared asset-level CellInfoScreen (#479)."""
from __future__ import annotations

import pytest
from textual.app import App
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from agent_toolkit_tui.screens.cell_info import CellInfoScreen, asset_info_body
from agent_toolkit_tui.skill_state import interactive_agents, SkillCell, SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _row(
    slug: str,
    *,
    scope: str = "global",
    linked: tuple[str, ...] = (),
    drifted: tuple[str, ...] = (),
    stray: tuple[str, ...] = (),
    description: str = "",
    state: str = "clean",
) -> SkillRow:
    cells = {
        (agent, scope): SkillCell(
            linked=agent in linked,
            drift=agent in drifted,
            skipped=False,
            stray=agent in stray,
        )
        for agent in interactive_agents()
    }
    return SkillRow(
        slug=slug,
        source=f"x/{slug}",
        ref="main",
        state=state,
        cells=cells,
        description=description,
    )


async def _open_skill_info(app: App, pilot, column: int = 0) -> CellInfoScreen:
    table = app.query_one("#skill-table", DataTable)
    table.cursor_coordinate = Coordinate(row=0, column=column)
    table.focus()
    await pilot.press("i")
    await pilot.pause()
    assert isinstance(app.screen, CellInfoScreen)
    return app.screen


@pytest.mark.asyncio
async def test_modal_renders_title_and_body() -> None:
    pushed: list[CellInfoScreen] = []

    class _A(App[None]):
        def on_mount(self) -> None:
            screen = CellInfoScreen(
                title="demo · Skill",
                body_markup="Skill [b]demo[/]\nSource: /tmp/x",
            )
            pushed.append(screen)
            self.push_screen(screen)

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        rendered = str(pushed[0].query_one("#cell-info-body").content)
        assert "demo" in rendered
        assert "/tmp/x" in rendered


@pytest.mark.asyncio
async def test_modal_dismisses_on_escape() -> None:
    class _A(App[None]):
        def on_mount(self) -> None:
            self.push_screen(CellInfoScreen(title="t", body_markup="b"))

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, CellInfoScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, CellInfoScreen)


@pytest.mark.parametrize(
    "row",
    [
        _row("journal", drifted=("claude-code",)),
        _row("journal", stray=("claude-code",)),
        _row("journal"),
    ],
    ids=("drifted-cell", "stray-cell", "unlinked-cell"),
)
@pytest.mark.asyncio
async def test_i_explains_the_asset_not_selected_cell_state(row: SkillRow) -> None:
    """Legacy cell-specific `i` cases now all render one predictable row panel."""

    class _A(App[None]):
        def compose(self):
            yield SkillGrid([row], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await _open_skill_info(app, pilot, column=2)
        body = screen._body_markup

        assert screen._title == "journal · Skill"
        assert "Source: x/journal" in body
        assert "Ref:    main" in body
        assert "State (global): clean" in body
        assert "skill doctor" not in body
        assert "Press [b]space" not in body


@pytest.mark.asyncio
async def test_asset_info_includes_description_when_present() -> None:
    row = _row("journal", description="An atomic-note journal skill.")

    class _A(App[None]):
        def compose(self):
            yield SkillGrid([row], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await _open_skill_info(app, pilot)
        assert "Description:" in screen._body_markup
        assert "An atomic-note journal skill." in screen._body_markup


@pytest.mark.asyncio
async def test_asset_info_plainly_reports_missing_description() -> None:
    class _A(App[None]):
        def compose(self):
            yield SkillGrid([_row("journal")], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await _open_skill_info(app, pilot)
        assert "No description in SKILL.md." in screen._body_markup
        assert "Description:" not in screen._body_markup


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["library", "clean"])
async def test_asset_info_names_the_scope_and_row_state(state: str) -> None:
    class _A(App[None]):
        def compose(self):
            yield SkillGrid([_row("journal", state=state)], id="g")

    app = _A()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = await _open_skill_info(app, pilot)
        assert f"State (global): {state}" in screen._body_markup


def test_asset_info_body_uses_em_dash_when_ref_is_unavailable() -> None:
    body = asset_info_body(
        asset_label="MCP",
        slug="demo",
        description=None,
        description_location="MCP definition",
        source="npx",
        ref=None,
        state="installed",
        scope="project",
    )
    assert "Ref:    —" in body
    assert "State (project): installed" in body
