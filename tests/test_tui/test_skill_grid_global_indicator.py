"""Render tests for the globally-installed indicator in the project view (#188)."""
from __future__ import annotations

import pytest
from rich.text import Text
from textual.app import App
from textual.widgets import DataTable

from agent_toolkit_tui.skill_state import INTERACTIVE_AGENTS, SkillCell, SkillRow
from agent_toolkit_tui.widgets.skill_grid import SkillGrid


def _linked() -> SkillCell:
    return SkillCell(linked=True, drift=False, skipped=False)


def _unlinked() -> SkillCell:
    return SkillCell(linked=False, drift=False, skipped=False)


def _drifted() -> SkillCell:
    return SkillCell(linked=False, drift=True, skipped=False)


def _skipped() -> SkillCell:
    return SkillCell(linked=True, drift=False, skipped=True)


def _row_with(
    slug: str,
    *,
    project_cells: dict[str, SkillCell] | None = None,
    global_cells: dict[str, SkillCell] | None = None,
) -> SkillRow:
    cells: dict[tuple[str, str], SkillCell] = {}
    if project_cells:
        for agent, cell in project_cells.items():
            cells[(agent, "project")] = cell
    if global_cells:
        for agent, cell in global_cells.items():
            cells[(agent, "global")] = cell
    return SkillRow(
        slug=slug, source=f"x/{slug}", ref="main",
        state="library", cells=cells,
    )


@pytest.mark.asyncio
async def test_project_scope_globally_linked_cell_shows_marker():
    """In project scope, a row that is globally linked for claude-code
    shows the 🌐 suffix on the claude-code cell."""
    row = _row_with(
        "alpha",
        project_cells={agent: _unlinked() for agent in INTERACTIVE_AGENTS},
        global_cells={
            "universal": _unlinked(),
            "claude-code": _linked(),
            "pi": _unlinked(),
        },
    )

    class _A(App):
        def compose(self):
            grid = SkillGrid([row], id="g")
            yield grid

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        # Force a rebuild so the new scope is reflected.
        table = a.query_one("#skill-table", DataTable)
        g._rebuild(table)  # type: ignore[attr-defined]
        await pilot.pause()
        rendered_rows = list(table.rows.keys())
        assert rendered_rows, "no rows rendered"
        row_key = rendered_rows[0]
        cols = list(table.columns.keys())
        cc_col_key = cols[1 + INTERACTIVE_AGENTS.index("claude-code")]
        pi_col_key = cols[1 + INTERACTIVE_AGENTS.index("pi")]
        cc_plain = Text.from_markup(str(table.get_cell(row_key, cc_col_key))).plain
        pi_plain = Text.from_markup(str(table.get_cell(row_key, pi_col_key))).plain
        assert "🌐" in cc_plain, f"claude-code cell missing marker: {cc_plain!r}"
        assert "🌐" not in pi_plain, f"pi cell unexpectedly shows marker: {pi_plain!r}"


@pytest.mark.asyncio
async def test_global_scope_view_does_not_show_marker():
    """In global scope, even a globally-linked row must not show 🌐.
    The marker is informative only when looking at the project view."""
    row = _row_with(
        "alpha",
        global_cells={
            "universal": _linked(),
            "claude-code": _linked(),
            "pi": _linked(),
        },
    )

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", SkillGrid)
        g.set_scope("global")
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        g._rebuild(table)  # type: ignore[attr-defined]
        await pilot.pause()
        row_key = list(table.rows.keys())[0]
        for agent in INTERACTIVE_AGENTS:
            col_idx = 1 + INTERACTIVE_AGENTS.index(agent)
            col_key = list(table.columns.keys())[col_idx]
            plain = Text.from_markup(str(table.get_cell(row_key, col_key))).plain
            assert "🌐" not in plain, (
                f"global-scope {agent} cell unexpectedly has marker: {plain!r}"
            )


@pytest.mark.asyncio
async def test_drifted_global_cell_does_not_show_marker():
    """A drifted global symlink is NOT a clean global install — no marker."""
    row = _row_with(
        "alpha",
        project_cells={agent: _unlinked() for agent in INTERACTIVE_AGENTS},
        global_cells={
            "universal": _unlinked(),
            "claude-code": _drifted(),
            "pi": _unlinked(),
        },
    )

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        g._rebuild(table)  # type: ignore[attr-defined]
        await pilot.pause()
        row_key = list(table.rows.keys())[0]
        cc_col_key = list(table.columns.keys())[1 + INTERACTIVE_AGENTS.index("claude-code")]
        plain = Text.from_markup(str(table.get_cell(row_key, cc_col_key))).plain
        assert "🌐" not in plain, f"drifted global cell shows marker: {plain!r}"


@pytest.mark.asyncio
async def test_skipped_global_cell_does_not_show_marker():
    """A skipped global cell (canonical-IS-dir) is informational, not a
    clean per-agent global link — no marker."""
    row = _row_with(
        "alpha",
        project_cells={agent: _unlinked() for agent in INTERACTIVE_AGENTS},
        global_cells={
            "universal": _skipped(),
            "claude-code": _unlinked(),
            "pi": _unlinked(),
        },
    )

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        g._rebuild(table)  # type: ignore[attr-defined]
        await pilot.pause()
        row_key = list(table.rows.keys())[0]
        u_col_key = list(table.columns.keys())[1 + INTERACTIVE_AGENTS.index("universal")]
        plain = Text.from_markup(str(table.get_cell(row_key, u_col_key))).plain
        assert "🌐" not in plain, f"skipped global cell shows marker: {plain!r}"


@pytest.mark.asyncio
async def test_per_agent_independence():
    """A row that is globally linked for universal but not pi shows the
    marker only on the universal cell."""
    row = _row_with(
        "alpha",
        project_cells={agent: _unlinked() for agent in INTERACTIVE_AGENTS},
        global_cells={
            "universal": _linked(),
            "claude-code": _unlinked(),
            "pi": _unlinked(),
        },
    )

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        g._rebuild(table)  # type: ignore[attr-defined]
        await pilot.pause()
        row_key = list(table.rows.keys())[0]
        cols = list(table.columns.keys())
        u_plain = Text.from_markup(str(table.get_cell(
            row_key, cols[1 + INTERACTIVE_AGENTS.index("universal")]))).plain
        cc_plain = Text.from_markup(str(table.get_cell(
            row_key, cols[1 + INTERACTIVE_AGENTS.index("claude-code")]))).plain
        pi_plain = Text.from_markup(str(table.get_cell(
            row_key, cols[1 + INTERACTIVE_AGENTS.index("pi")]))).plain
        assert "🌐" in u_plain, f"universal cell missing marker: {u_plain!r}"
        assert "🌐" not in cc_plain, f"claude-code cell has marker: {cc_plain!r}"
        assert "🌐" not in pi_plain, f"pi cell has marker: {pi_plain!r}"


@pytest.mark.asyncio
async def test_project_scope_no_global_cells_in_row_does_not_crash():
    """When a row carries no (agent, 'global') cells at all (e.g. callers
    that passed home=None to build_skill_rows), the marker simply does not
    render — no AttributeError, no crash (#188)."""
    row = _row_with(
        "alpha",
        project_cells={agent: _unlinked() for agent in INTERACTIVE_AGENTS},
        global_cells=None,
    )

    class _A(App):
        def compose(self):
            yield SkillGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        g = a.query_one("#g", SkillGrid)
        g.set_scope("project")
        await pilot.pause()
        table = a.query_one("#skill-table", DataTable)
        g._rebuild(table)  # type: ignore[attr-defined]
        await pilot.pause()
        row_key = list(table.rows.keys())[0]
        cols = list(table.columns.keys())
        for agent in INTERACTIVE_AGENTS:
            col_key = cols[1 + INTERACTIVE_AGENTS.index(agent)]
            plain = Text.from_markup(str(table.get_cell(row_key, col_key))).plain
            assert "🌐" not in plain, (
                f"row without global cells should not show marker on {agent}: {plain!r}"
            )
