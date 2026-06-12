"""Render tests for the agents-tab globally-installed indicator (#374).

Mirrors test_skill_grid_global_indicator.py (#188). Harness names beyond
"standard" are derived (INTERACTIVE_HARNESSES), so tests index into the
tuple instead of hard-coding names.
"""
from __future__ import annotations

import pytest
from rich.text import Text
from textual.app import App
from textual.widgets import DataTable

from agent_toolkit_tui.agent_state import INTERACTIVE_HARNESSES, AgentCell, AgentRow
from agent_toolkit_tui.widgets.agent_grid import AgentGrid

_H0 = INTERACTIVE_HARNESSES[0]  # "standard"
_H1 = INTERACTIVE_HARNESSES[1]  # first non-standard main harness


def _row_with(
    slug: str,
    *,
    state: str = "installed",
    project_cells: dict[str, AgentCell] | None = None,
    global_cells: dict[str, AgentCell] | None = None,
) -> AgentRow:
    cells: dict[tuple[str, str], AgentCell] = {}
    for harness, cell in (project_cells or {}).items():
        cells[(harness, "project")] = cell
    for harness, cell in (global_cells or {}).items():
        cells[(harness, "global")] = cell
    return AgentRow(slug=slug, source=f"x/{slug}", ref="main", state=state, cells=cells)


async def _rendered_plain(app: App, pilot, harness: str) -> str:
    table = app.query_one("#agent-table", DataTable)
    grid = app.query_one("#g", AgentGrid)
    grid._rebuild(table)  # type: ignore[attr-defined]
    await pilot.pause()
    row_key = list(table.rows.keys())[0]
    col_key = list(table.columns.keys())[1 + list(INTERACTIVE_HARNESSES).index(harness)]
    return Text.from_markup(str(table.get_cell(row_key, col_key))).plain


@pytest.mark.asyncio
async def test_project_scope_globally_linked_cell_shows_marker():
    """In project scope, a cell whose harness is globally linked shows 🌐;
    a sibling harness without a global link does not."""
    row = _row_with(
        "alpha",
        project_cells={h: AgentCell(linked=False) for h in INTERACTIVE_HARNESSES},
        global_cells={_H0: AgentCell(linked=True), _H1: AgentCell(linked=False)},
    )

    class _A(App):
        def compose(self):
            yield AgentGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", AgentGrid).set_scope("project")
        await pilot.pause()
        assert "🌐" in await _rendered_plain(a, pilot, _H0)
        assert "🌐" not in await _rendered_plain(a, pilot, _H1)


@pytest.mark.asyncio
async def test_global_scope_view_does_not_show_marker():
    """In global scope, even a globally-linked cell must not show 🌐."""
    row = _row_with(
        "alpha",
        global_cells={h: AgentCell(linked=True) for h in INTERACTIVE_HARNESSES},
    )

    class _A(App):
        def compose(self):
            yield AgentGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", AgentGrid).set_scope("global")
        await pilot.pause()
        for harness in INTERACTIVE_HARNESSES:
            assert "🌐" not in await _rendered_plain(a, pilot, harness)


@pytest.mark.asyncio
async def test_not_applicable_project_cell_still_shows_marker():
    """A harness with no project cell (not applicable at project scope) but a
    linked global cell renders the marker next to the em-dash base — matching
    the skills tab, where the marker appends to whatever the base glyph is."""
    row = _row_with(
        "alpha",
        project_cells={},
        global_cells={_H0: AgentCell(linked=True)},
    )

    class _A(App):
        def compose(self):
            yield AgentGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", AgentGrid).set_scope("project")
        await pilot.pause()
        plain = await _rendered_plain(a, pilot, _H0)
        assert "—" in plain and "🌐" in plain


@pytest.mark.asyncio
async def test_unlisted_row_shows_marker():
    """#360 state badges and the marker are independent — an unlisted row
    with a globally-linked cell shows 🌐."""
    row = _row_with(
        "alpha",
        state="unlisted",
        project_cells={h: AgentCell(linked=True) for h in INTERACTIVE_HARNESSES},
        global_cells={_H0: AgentCell(linked=True)},
    )

    class _A(App):
        def compose(self):
            yield AgentGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", AgentGrid).set_scope("project")
        await pilot.pause()
        assert "🌐" in await _rendered_plain(a, pilot, _H0)


@pytest.mark.asyncio
async def test_no_global_cells_no_marker_no_crash():
    """Rows without any (harness, 'global') cells (e.g. home=None callers)
    simply render no marker — no KeyError, no crash."""
    row = _row_with(
        "alpha",
        project_cells={h: AgentCell(linked=True) for h in INTERACTIVE_HARNESSES},
    )

    class _A(App):
        def compose(self):
            yield AgentGrid([row], id="g")

    a = _A()
    async with a.run_test() as pilot:
        a.query_one("#g", AgentGrid).set_scope("project")
        await pilot.pause()
        for harness in INTERACTIVE_HARNESSES:
            assert "🌐" not in await _rendered_plain(a, pilot, harness)
