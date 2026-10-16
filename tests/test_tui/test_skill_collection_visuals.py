"""Render the complete collection acceptance matrix from disposable assets."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from textual.coordinate import Coordinate
from textual.widgets import Static

from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from tests.test_cli.test_skill_collection_reconcile import legacy, git


NAMES = [
    "aj-bootstrap",
    "aj-demo",
    "aj-epic",
    "aj-git",
    "aj-issue",
    "aj-pm",
    "aj-pr-review",
    "aj-provision-agents",
    "aj-run",
    "aj-test-plane",
    "repo-recon",
]


@pytest.fixture(name="tmp_path")
def public_visual_fixture_root():
    with TemporaryDirectory(
        prefix="atk-529-visual-", dir="/tmp" if Path("/tmp").is_dir() else None
    ) as directory:
        yield Path(directory).resolve()


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(120, 40), (180, 50)])
async def test_visual_matrix(legacy, size, tmp_path, monkeypatch):
    directory = os.environ.get("ATK_529_VISUAL_DIR")
    output = Path(directory).resolve() if directory else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    workspace = tmp_path / "collection-demo"
    workspace.mkdir()
    git(workspace, "init", "-q", "-b", "main")
    monkeypatch.chdir(workspace)
    for old, name in zip(sorted(legacy.glob("workflow-*")), NAMES):
        old.rename(legacy / name)
        (legacy / name / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name} acceptance fixture\n---\nFixture only.\n"
        )
    git(legacy, "add", ".")
    git(legacy, "commit", "-qm", "realistic fixture names")
    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=size) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)

        async def capture(name):
            await pilot.pause()
            if output:
                app.save_screenshot(
                    filename=f"{size[0]}x{size[1]}-{name}.svg", path=str(output)
                )

        def toggle(name):
            grid.cursor_to_cell(row_slug=name, agent_name="standard")
            grid.action_toggle_cell()

        assert grid.row_count == 11 and grid.collection_count == 1
        await capture("01-all-hierarchy-names-totals-unavailable")
        toggle("aj-bootstrap")
        await capture("02-mixed-and-pending-removal-child-override")
        grid._toggle_at(Coordinate(0, 1))
        assert not grid.pending_entries()
        await capture("03-mixed-click-all")
        grid._toggle_at(Coordinate(0, 1))
        assert len(grid.pending_entries()) == 11
        await capture("04-none-queued")
        app.action_revert()
        assert not grid.pending_entries()
        await capture("05-revert-no-writes")
        grid._toggle_at(Coordinate(0, 0))
        grid._toggle_at(Coordinate(0, 1))
        assert len(grid.pending_entries()) == 11
        await capture("06-collapsed-full-membership")
        app.action_revert()
        grid._toggle_at(Coordinate(0, 0))
        grid.set_filter("aj-provision")
        grid._toggle_at(Coordinate(0, 1))
        assert len(grid.pending_entries()) == 11
        await capture("07-filter-hidden-full-membership")
        app.action_revert()
        grid.set_filter("")
        # The first actual conversion is deliberately failed, leaving inherited
        # exposure and pending deltas visible rather than a false disabled state.
        conflict = Path.home() / ".agents/skills/aj-issue"
        conflict.symlink_to(legacy / "aj-demo")
        toggle("aj-bootstrap")
        app.action_apply()
        assert grid.pending_entries()
        assert (Path.home() / ".agents/skills/wrapper").resolve() == legacy
        await capture("08-legacy-failure-truthful")
        conflict.unlink()
        app.action_apply()
        assert not grid.pending_entries()
        assert not (Path.home() / ".agents/skills/wrapper").exists()
        assert len(list((Path.home() / ".agents/skills").iterdir())) == 10
        await capture("09-apply-ten-real-links-mixed")
        grid._toggle_at(Coordinate(0, 1))
        assert grid.pending_entries() == {
            ("global", "standard", "aj-bootstrap"): "link"
        }
        await capture("10-mixed-click-all-pending-child-install")
        app.action_revert()
        await capture("11-revert-to-actual-mixed")
        grid._toggle_at(Coordinate(0, 1))
        app.action_apply()
        grid._toggle_at(Coordinate(0, 1))
        app.action_apply()
        assert not list((Path.home() / ".agents/skills").iterdir())
        await capture("12-none-applied")
        grid._toggle_at(Coordinate(0, 1))
        app.action_apply()
        assert len(list((Path.home() / ".agents/skills").iterdir())) == 11
        await capture("13-all-idempotent-retry")
        payload = legacy / "aj-bootstrap/SKILL.md"
        payload.unlink()
        app.action_refresh()
        assert "!" in grid._cell_glyph(row=grid._visible_rows()[0], agent="standard")
        bar = str(app.query_one("#status-bar", Static).render())
        assert "10 linked" in bar and "1 broken" in bar
        await capture("14-missing-document-not-healthy")
        grid._toggle_at(Coordinate(0, 1))
        app.action_apply()
        assert grid.pending_entries() == {
            ("global", "standard", "aj-bootstrap"): "link"
        }
        assert not payload.exists()
        await capture("15-missing-document-apply-refused")
        app.action_revert()
        assert not payload.exists()
