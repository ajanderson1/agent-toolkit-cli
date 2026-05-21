"""Tests for the description (column index 1) and source (last column)
columns added to SkillGrid in #182."""
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
async def test_description_column_is_second():
    from textual.app import App
    from textual.widgets import DataTable

    class _A(App):
        def compose(self):
            yield SkillGrid([
                _row("alpha", description="first skill"),
                _row("beta", description="second skill"),
            ], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        labels = [str(c.label) for c in table.columns.values()]
        assert labels[0] == "SKILL"
        assert labels[1] == "Description"
        # Per-row cell text matches each row's description.
        row_keys = list(table.rows.keys())
        # rows are sorted by slug ("alpha" then "beta")
        cells_alpha = list(table.get_row(row_keys[0]))
        cells_beta = list(table.get_row(row_keys[1]))
        assert cells_alpha[1] == "first skill"
        assert cells_beta[1] == "second skill"


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
async def test_description_empty_for_library_rows():
    """A library-state row with no description renders an empty cell, not 'None'."""
    from textual.app import App
    from textual.widgets import DataTable

    class _A(App):
        def compose(self):
            yield SkillGrid([_row("alpha", description="", state="library")], id="g")

    a = _A()
    async with a.run_test() as pilot:
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        row_keys = list(table.rows.keys())
        cells = list(table.get_row(row_keys[0]))
        assert cells[1] == ""


@pytest.mark.asyncio
async def test_new_columns_do_not_break_agent_toggling():
    """The new columns shift agent columns right by one; toggle binding still
    targets the right agent."""
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
