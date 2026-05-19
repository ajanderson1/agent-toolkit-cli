"""Render-level test: 🌐 suffix appears on project-scope cells whose user-scope cell is linked."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_tui.state import AssetRow, CellState, InventoryState
from agent_toolkit_tui.widgets.asset_grid import AssetGrid


def _row(slug: str, *, claude_user: str, claude_project: str) -> AssetRow:
    return AssetRow(
        slug=slug,
        kind="skill",
        origin="first-party",
        description="",
        path=Path(f"/fake/{slug}"),
        declared_harnesses=("claude",),
        cells={
            ("claude", "user"):    CellState(status=claude_user,    target_path=None, allowlisted=True),
            ("claude", "project"): CellState(status=claude_project, target_path=None, allowlisted=True),
        },
    )


def _state(*rows: AssetRow) -> InventoryState:
    return InventoryState(toolkit_root=Path("/fake"), rows=rows, all_harnesses=("claude",))


@pytest.mark.parametrize("user_status", ["linked", "linked-matches", "linked-drifted"])
def test_project_scope_cell_gets_globe_suffix_when_user_scope_linked(user_status):
    state = _state(_row("alpha", claude_user=user_status, claude_project="linked"))
    grid = AssetGrid(state)
    grid._scope = "project"
    cell_text = grid._cell_glyph(row=state.rows[0], harness="claude")
    assert "🌐" in cell_text


def test_project_scope_cell_no_globe_when_user_scope_not_linked():
    state = _state(_row("alpha", claude_user="unlinked", claude_project="linked"))
    grid = AssetGrid(state)
    grid._scope = "project"
    cell_text = grid._cell_glyph(row=state.rows[0], harness="claude")
    assert "🌐" not in cell_text


def test_user_scope_view_never_renders_globe():
    state = _state(_row("alpha", claude_user="linked", claude_project="linked"))
    grid = AssetGrid(state)
    grid._scope = "user"
    cell_text = grid._cell_glyph(row=state.rows[0], harness="claude")
    assert "🌐" not in cell_text


def test_pending_op_takes_precedence_over_globe_suffix():
    state = _state(_row("alpha", claude_user="linked", claude_project="unlinked"))
    grid = AssetGrid(state)
    grid._scope = "project"
    grid._pending[("project", "claude", "skill", "alpha")] = "link"
    cell_text = grid._cell_glyph(row=state.rows[0], harness="claude")
    # Pending overlay should be visible; globe is dropped to keep cell readable.
    assert "[yellow]" in cell_text
    assert "🌐" not in cell_text


def test_no_globe_when_user_scope_cell_absent():
    """A row that lacks a user-scope cell for the harness must not crash
    and must not render the globe."""
    row = AssetRow(
        slug="alpha",
        kind="skill",
        origin="first-party",
        description="",
        path=Path("/fake/alpha"),
        declared_harnesses=("claude",),
        cells={
            ("claude", "project"): CellState(status="linked", target_path=None, allowlisted=True),
        },
    )
    state = InventoryState(toolkit_root=Path("/fake"), rows=(row,), all_harnesses=("claude",))
    grid = AssetGrid(state)
    grid._scope = "project"
    cell_text = grid._cell_glyph(row=state.rows[0], harness="claude")
    assert "🌐" not in cell_text
