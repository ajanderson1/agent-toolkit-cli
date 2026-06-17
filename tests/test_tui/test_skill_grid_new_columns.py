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
        assert "Skill ⓘ" in labels
        assert not any("SKILL" in label for label in labels)
        assert any(label.startswith("Standard (") for label in labels)
        assert not any("Claude Code" in label for label in labels)
        assert not any("Gemini CLI" in label for label in labels)
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


def test_unlisted_state_markup():
    """#360: unlisted rows render with a warning (yellow) tint, distinct from dim library."""
    from agent_toolkit_tui.widgets.skill_grid import _STATE_MARKUP
    assert "unlisted" in _STATE_MARKUP
    assert "yellow" in _STATE_MARKUP["unlisted"]
    # library stays dim — the two states must be visually distinct.
    assert "dim" in _STATE_MARKUP["library"]


def test_unlisted_in_state_legend():
    """#360: the State column's `i` legend explains the unlisted badge."""
    from agent_toolkit_tui.column_info import get_column_info
    info = get_column_info("state")
    assert any("unlisted" in line for line in info.lines)


def test_build_skill_rows_project_scope_falls_back_to_library_description(
    git_sandbox, tmp_path, monkeypatch,
):
    """At project scope, when the project canonical is absent (state='library'),
    SkillRow.description reads from the library canonical instead of returning empty."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main
    from agent_toolkit_tui.skill_state import build_skill_rows

    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    # Only add to library; do NOT install at project scope.
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output

    # Stamp a description into the library canonical's SKILL.md.
    library_canonical = library_root / "demo"
    skill_md = library_canonical / "SKILL.md"
    skill_md.write_text(
        "---\nname: demo\ndescription: Library description value\n---\n\nBody.\n"
    )

    rows = build_skill_rows(scope="project", home=None, project=project)
    assert len(rows) == 1
    row = rows[0]
    assert row.state == "library", f"precondition: expected state=library, got {row.state}"
    assert row.description == "Library description value", (
        f"description should fall back to the library canonical, got {row.description!r}"
    )
