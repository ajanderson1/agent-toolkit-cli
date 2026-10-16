from pathlib import Path

import pytest
from click.testing import CliRunner
from textual.coordinate import Coordinate

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import library_lock_path
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.widgets.skill_grid import SkillGrid
from tests.test_cli.test_skill_collection_registration import source, invoke


@pytest.mark.asyncio
async def test_ref_parents_are_independent_but_explicit_source_install_spans_refs(
    source, tmp_path, monkeypatch
):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    assert invoke(source).exit_code == 0
    for name in ("alpha", "beta"):
        result = invoke(
            source, "--skill", name, "--slug", f"{name}-other", "--ref", "other"
        )
        assert result.exit_code == 0, result.output
    app = TUIApp()
    app._scope = "global"
    async with app.run_test(size=(180, 50)) as pilot:
        app.action_asset_type("skill")
        await pilot.pause()
        grid = app.query_one("#skill-grid", SkillGrid)
        assert grid.row_count == 4 and grid.collection_count == 2
        grid._toggle_at(Coordinate(0, 1))
        assert set(grid.pending_entries()) == {
            ("global", "standard", "alpha"),
            ("global", "standard", "beta"),
        }
        app.action_apply()
        await pilot.pause()
        assert (home / ".agents/skills/alpha").is_symlink()
        assert not (home / ".agents/skills/alpha-other").exists()
        assert read_lock(library_lock_path()).skills["alpha-other"].ref == "other"
    result = CliRunner().invoke(
        main, ["skill", "install", "--source", "local/repo", "--agents", "standard"]
    )
    assert result.exit_code == 0, result.output
    assert {p.name for p in (home / ".agents/skills").iterdir()} == {
        "alpha",
        "beta",
        "alpha-other",
        "beta-other",
    }
