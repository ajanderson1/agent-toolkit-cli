"""Typed catalogue candidates use existing grids without downloads on discovery."""
import json

import pytest
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from tests.test_cli.test_asset_catalog import entry, manifest
from tests.test_cli.test_asset_catalog_acquire import subscribe
from tests.test_cli.test_reground import sandbox, repo, git


def test_pure_candidate_rows_and_directory_targets(tmp_path, sandbox):
    subscribe(tmp_path, entry(entryFile="AGENTS.md"), entry("command"), entry("pi-extension"))
    from agent_toolkit_cli.skill_catalog import read_catalog
    from agent_toolkit_tui.agent_state import build_agent_rows
    from agent_toolkit_tui.command_state import build_command_rows
    from agent_toolkit_tui.pi_extension_state import build_pi_rows
    snapshot = read_catalog()
    agents = build_agent_rows(scope="global", home=sandbox, project=None, catalog_snapshot=snapshot)
    commands = build_command_rows(scope="global", home=sandbox, project=None, catalog_snapshot=snapshot)
    extensions = build_pi_rows(home=sandbox, catalog_snapshot=snapshot)
    assert agents[0].catalog_only and ("pi", "global") in agents[0].cells
    assert ("standard", "global") not in agents[0].cells
    assert commands[0].catalog_only and not commands[0].cells[("pi", "global")].linked
    assert extensions[0].catalog_only and extensions[0].origin == "catalog"
    assert not (sandbox / ".agent-toolkit/agents-lock.json").exists()


@pytest.mark.asyncio
async def test_one_snapshot_all_grids_revert_and_cross_kind_apply(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"reviewer.md": "Role", "COMMAND.md": "Prompt", "index.ts": "export default () => {}"})
    subscribe(tmp_path, *(entry(kind, source=source.as_uri()) for kind in ("agent", "command", "pi-extension")))
    monkeypatch.chdir(tmp_path)
    from agent_toolkit_cli import skill_catalog
    original = skill_catalog.read_catalog
    calls = []
    def counted(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(skill_catalog, "read_catalog", counted)
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.agent_grid import AgentGrid
    from agent_toolkit_tui.widgets.command_grid import CommandGrid
    from agent_toolkit_tui.widgets.pi_grid import PiGrid
    app = TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        agents, commands, extensions = (app.query_one(cls) for cls in (AgentGrid, CommandGrid, PiGrid))
        assert agents.row_slugs == commands.row_slugs == extensions.row_slugs == ["reviewer"]
        assert len(calls) == 1
        app._refresh_command_view()
        app._refresh_agent_view()
        assert len(calls) == 1
        for grid in (agents, commands):
            grid.restore_pending({("project", "pi", "reviewer"): "link"})
        extensions.restore_pending({("project", "reviewer"): "link"})
        assert not (sandbox / ".agent-toolkit/agents-lock.json").exists()
        app.action_revert()
        assert all(not grid.pending_entries() for grid in (agents, commands, extensions))
        for grid in (agents, commands):
            grid.restore_pending({("project", "pi", "reviewer"): "link"})
        extensions.restore_pending({("project", "reviewer"): "link"})
        calls.clear()
        app.action_apply()
        assert len(calls) == 1  # Shared revalidation for the entire cross-kind Apply.
        assert (tmp_path / ".pi/agents/reviewer.md").exists()
        assert (tmp_path / ".pi/prompts/reviewer.md").exists()
        assert (tmp_path / ".pi/extensions/reviewer").exists()
        assert all(not grid.pending_entries() for grid in (agents, commands, extensions))


@pytest.mark.asyncio
async def test_changed_selector_remains_pending_and_never_acquired(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"COMMAND.md": "Prompt"})
    cat = subscribe(tmp_path, entry("command", source=source.as_uri()))
    monkeypatch.chdir(tmp_path)
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.command_grid import CommandGrid
    app = TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        grid = app.query_one(CommandGrid)
        key = ("project", "pi", "reviewer")
        grid.restore_pending({key: "link"})
        data = json.loads((cat / "catalog.json").read_text())
        data["entries"][0]["ref"] = "different"
        (cat / "catalog.json").write_text(json.dumps(data))
        git(cat, "add", ".")
        git(cat, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "change")
        result = app._apply_command_pending()
        assert result.failed == 1 and "changed" in " ".join(result.errors)
        assert grid.pending_entries() == {key: "link"}
        assert not (sandbox / ".agent-toolkit/commands-lock.json").exists()


@pytest.mark.asyncio
async def test_npm_candidate_is_read_only_and_info_explains_install(tmp_path, sandbox, monkeypatch):
    subscribe(tmp_path, dict(kind="pi-extension", key="native", description="Native package",
                            sourceType="npm", source="npm:@example/tools@1.2.3"))
    monkeypatch.chdir(tmp_path)
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.widgets.pi_grid import PiGrid
    app = TUIApp()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        grid = app.query_one(PiGrid)
        assert len(grid._rows) == 1 and grid._rows[0].catalog_only
        grid._toggle_at(Coordinate(0, 1))
        assert grid.pending_entries() == {}
        body = grid._info_body(row=grid._rows[0], scope="project")
        assert "catalog install native --scope project" in body
        assert "not installed" in body.lower()
