import pytest
from textual.app import App, ComposeResult

from agent_toolkit_tui.skill_state import SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


@pytest.mark.asyncio
async def test_skill_grid_renders_rows():
    rows = [
        SkillRow(slug="journal", source="ajanderson1/journal", ref="main", state="clean"),
        SkillRow(slug="aj-workflow", source="ajanderson1/aj-workflow", ref="main", state="dirty"),
    ]

    class _Harness(App):
        def compose(self) -> ComposeResult:
            yield SkillGrid(rows, id="skill-grid")

    async with _Harness().run_test() as pilot:
        grid = pilot.app.query_one(SkillGrid)
        assert grid.row_count == 2
        assert grid.row_slugs == ["aj-workflow", "journal"]


@pytest.mark.asyncio
async def test_skill_grid_empty():
    class _Harness(App):
        def compose(self) -> ComposeResult:
            yield SkillGrid([], id="skill-grid")

    async with _Harness().run_test() as pilot:
        grid = pilot.app.query_one(SkillGrid)
        assert grid.row_count == 0
