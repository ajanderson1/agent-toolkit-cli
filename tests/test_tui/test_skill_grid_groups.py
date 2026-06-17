"""Standard column on the skill grid (#351).

Single-line headers: the Standard column leads; everything after it is
implicitly non-standard. The long tail of harnesses is CLI-only (post-demo
AJ decision — the collapsible pseudo-column was removed).
"""
from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from agent_toolkit_cli.skill_agents import get_standard_agents
from agent_toolkit_tui.composition import skills_nonstandard_main
from agent_toolkit_tui.display_names import harness_label, standard_label
from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _row(slug: str, *, scope: str = "global") -> SkillRow:
    cells = {(a, scope): SkillCell(linked=False, drift=False, skipped=False)
             for a in INTERACTIVE_AGENTS}
    return SkillRow(
        slug=slug, source=f"x/{slug}", ref="main",
        state="clean", cells=cells,
    )


class _GridApp(App):
    def __init__(self, rows: list[SkillRow]) -> None:
        super().__init__()
        self._fixture_rows = rows

    def compose(self) -> ComposeResult:
        yield SkillGrid(self._fixture_rows, id="g")


@pytest.mark.asyncio
async def test_columns_are_standard_plus_noncovered_main():
    app = _GridApp([_row("alpha")])
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#skill-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        # slug + Standard (N) + non-covered main harnesses + state + source
        assert labels[0] == "Skill ⓘ"
        assert labels[1] == f"{standard_label(len(get_standard_agents()))} ⓘ"
        for i, agent in enumerate(skills_nonstandard_main(), start=2):
            assert harness_label(agent) in labels[i]
        assert not any("Claude Code" in label for label in labels)
        # Standard-covered main harnesses get NO own column.
        assert not any("Codex" in l or "Gemini" in l or "Cursor" in l
                       or "OpenCode" in l for l in labels), labels
        # No long-tail pseudo-column, no group tags, single-line labels only.
        assert not any("… +" in l or "STANDARD" in l or "NON-STD" in l
                       or "\n" in l for l in labels), labels
        # Layout is exactly: slug + N agents + state + source.
        assert len(labels) == len(INTERACTIVE_AGENTS) + 3
