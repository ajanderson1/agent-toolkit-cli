from pathlib import Path

import pytest
from textual.coordinate import Coordinate
from textual.widgets import Static

from agent_toolkit_tui.app import TUIApp

from agent_toolkit_cli.skill_collections import apply_selection, catalog, exposed
from agent_toolkit_cli.skill_paths import library_lock_path
from agent_toolkit_tui.skill_state import build_skill_rows
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from tests.test_cli.test_skill_collection_reconcile import legacy


def test_missing_skill_document_is_not_healthy_selection_or_parent_all(legacy):
    group = catalog(scope="global", home=Path.home(), project=None)[0]
    apply_selection(
        group,
        {"standard": set(group.children)},
        scope="global",
        home=Path.home(),
        project=None,
    )
    (legacy / "workflow-00/SKILL.md").unlink()
    before = library_lock_path().read_bytes()
    rows = build_skill_rows(scope="global", home=Path.home(), project=None)
    grid = SkillGrid(rows)
    child = next(r for r in rows if r.slug == "workflow-00")
    parent = grid._visible_rows()[0]
    assert child.state == "missing"
    assert not child.cells[("standard", "global")].linked
    assert not exposed(
        group.children[child.slug],
        group,
        "standard",
        scope="global",
        home=Path.home(),
        project=None,
    )
    assert not grid._effective(child, "standard")
    assert "[green]" not in grid._cell_glyph(row=parent, agent="standard")
    assert "!" in grid._cell_glyph(row=child, agent="standard")
    assert library_lock_path().read_bytes() == before
    # A valid document with local edits is still usable; dirty is not missing.
    (legacy / "workflow-00/SKILL.md").write_text(
        "---\nname: workflow-00\ndescription: repaired locally\n---\nchanged\n"
    )
    repaired = build_skill_rows(scope="global", home=Path.home(), project=None)
    repaired_grid = SkillGrid(repaired)
    restored = next(r for r in repaired if r.slug == child.slug)
    assert restored.state == "dirty" and restored.cells[("standard", "global")].linked
    assert repaired_grid._effective(restored, "standard")
    assert "[green]" in repaired_grid._cell_glyph(
        row=repaired_grid._visible_rows()[0], agent="standard"
    )
    assert library_lock_path().read_bytes() == before


@pytest.mark.asyncio
async def test_missing_payload_apply_retains_request_and_never_recreates_document(
    legacy,
):
    group = catalog(scope="global", home=Path.home(), project=None)[0]
    apply_selection(
        group,
        {"standard": set(group.children)},
        scope="global",
        home=Path.home(),
        project=None,
    )
    payload = legacy / "workflow-00/SKILL.md"
    payload.unlink()
    before = library_lock_path().read_bytes()
    index = (legacy / ".git/index").read_bytes()
    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=(120, 40)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        assert "!" in grid._cell_glyph(row=grid._visible_rows()[0], agent="standard")
        grid._toggle_at(Coordinate(0, 1))
        assert grid.pending_entries() == {("global", "standard", "workflow-00"): "link"}
        app.action_apply()
        await pilot.pause()
        assert grid.pending_entries() == {("global", "standard", "workflow-00"): "link"}
        assert "apply failed" in str(app.query_one("#footer-pending", Static).render())
        assert not payload.exists()
        assert library_lock_path().read_bytes() == before
        assert (legacy / ".git/index").read_bytes() == index
        app.action_revert()
        assert not grid.pending_entries()
        assert not payload.exists() and library_lock_path().read_bytes() == before
