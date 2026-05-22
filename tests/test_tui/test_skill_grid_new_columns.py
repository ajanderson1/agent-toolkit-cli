"""Tests for the source column and the description-into-slug-info flow.

The `description` field still lives on SkillRow (sourced from each skill's
SKILL.md frontmatter); it is surfaced via the slug-cell info modal rather
than a dedicated column. See test_cell_info.py for the slug-info path.
"""
from __future__ import annotations

import pytest

from agent_toolkit_tui.skill_state import (
    INTERACTIVE_AGENTS,
    SkillCell,
    SkillRow,
    _read_skill_description,
)
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _row(slug: str, *, description: str = "", source: str = "", state="clean") -> SkillRow:
    cells = {(a, "global"): SkillCell(linked=False, drift=False, skipped=False)
             for a in INTERACTIVE_AGENTS}
    return SkillRow(
        slug=slug,
        source=source or f"x/{slug}",
        ref="main",
        state=state,
        cells=cells,
        description=description,
    )


@pytest.mark.asyncio
async def test_source_column_is_last():
    from textual.app import App
    from textual.widgets import DataTable

    class _A(App):
        def compose(self):
            yield SkillGrid([
                _row("alpha", source="git@github.com:foo/bar.git"),
            ], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert labels[-1] == "Source"
        row_keys = list(table.rows.keys())
        cells = list(table.get_row(row_keys[0]))
        assert cells[-1] == "git@github.com:foo/bar.git"


@pytest.mark.asyncio
async def test_agent_toggling_targets_correct_column():
    """slug at col 0, agents start at col 1. cursor_to_cell + space queues
    a link for the right agent."""
    from textual.app import App

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        g = a.query_one("#g", SkillGrid)
        g.cursor_to_cell(row_slug="alpha", agent_name="claude-code")
        await pilot.pause()
        await pilot.press("space")
        assert g.pending_entries() == {("global", "claude-code", "alpha"): "link"}


def test_read_skill_description_missing_dir(tmp_path):
    assert _read_skill_description(tmp_path / "does-not-exist") == ""


def test_read_skill_description_missing_skill_md(tmp_path):
    (tmp_path / "alpha").mkdir()
    assert _read_skill_description(tmp_path / "alpha") == ""


def test_read_skill_description_no_frontmatter(tmp_path):
    d = tmp_path / "alpha"
    d.mkdir()
    (d / "SKILL.md").write_text("# Just a heading\n\nNo frontmatter here.\n")
    assert _read_skill_description(d) == ""


def test_read_skill_description_happy_path(tmp_path):
    d = tmp_path / "alpha"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: A short description\n---\n\nBody.\n"
    )
    assert _read_skill_description(d) == "A short description"


def test_read_skill_description_collapses_whitespace(tmp_path):
    d = tmp_path / "alpha"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: |\n  multi\n  line\n  desc\n---\n"
    )
    # YAML literal block keeps newlines; we collapse to spaces.
    assert _read_skill_description(d) == "multi line desc"


def test_read_skill_description_no_key(tmp_path):
    d = tmp_path / "alpha"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: alpha\n---\n")
    assert _read_skill_description(d) == ""
