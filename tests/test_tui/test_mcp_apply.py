import json

import pytest

import agent_toolkit_cli.mcp_install as mcp_install
from agent_toolkit_cli.mcp_lock import (
    McpLockEntry,
    lock_path_for_scope,
    read_lock,
    write_lock,
)
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.mcp_state import McpRow
from agent_toolkit_tui.widgets.mcp_grid import McpGrid


@pytest.mark.asyncio
async def test_apply_groups_adds_and_calls_facade(monkeypatch):
    calls = []

    def _fake_apply(*, slug, harnesses, scope, library_root, home, project=None, force=False):
        calls.append(("apply", slug, tuple(sorted(harnesses)), scope))
        return mcp_install.ApplyResult(installed=list(harnesses), skipped=[], collisions=[])

    monkeypatch.setattr(mcp_install, "apply", _fake_apply)

    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("mcp")
        await pilot.pause()
        grid = app.query_one("#mcp-grid", McpGrid)
        grid.set_scope("project")
        grid.set_rows([McpRow(slug="ctx7", source="npx", pin=None,
                              state="library", cells={})])
        # Queue a standard link directly via the pending dict API.
        grid.restore_pending({("project", "standard", "ctx7"): "link"})
        await pilot.pause()
        app._apply_mcp_pending()
        await pilot.pause()

    assert ("apply", "ctx7", ("standard",), "project") in calls


@pytest.mark.asyncio
async def test_apply_dispatch_routes_mcp_not_agent(monkeypatch):
    # F-else-trap guard: with MCP active, action_apply (^s) must call
    # _apply_mcp_pending, NOT fall through to the agent catch-all.
    routed = {"mcp": False, "agent": False}
    monkeypatch.setattr(TUIApp, "_apply_mcp_pending",
                        lambda self: routed.__setitem__("mcp", True))
    monkeypatch.setattr(TUIApp, "_apply_agent_pending",
                        lambda self: routed.__setitem__("agent", True))
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("mcp")
        await pilot.pause()
        app.action_apply()
        await pilot.pause()
    assert routed["mcp"] is True and routed["agent"] is False


@pytest.mark.asyncio
async def test_apply_standard_collapses_legacy_rows_real_facade(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    lib = home / ".agent-toolkit" / "mcps"
    (lib / "ctx7").mkdir(parents=True)
    (lib / "ctx7" / "config.json").write_text(
        json.dumps({"command": "npx", "args": ["-y", "ctx7"]}), encoding="utf-8")
    # Legacy project lock: separate claude-code + pi rows (one shared .mcp.json).
    write_lock(lock_path_for_scope("project", home=home, project=project), {
        "ctx7": [McpLockEntry("ctx7", "claude-code", "npx", None),
                 McpLockEntry("ctx7", "pi", "npx", None)],
    })
    # Point the TUI's roots at tmp dirs (override the SSOT, not Path.cwd inline).
    monkeypatch.setattr(
        TUIApp, "_scope_to_roots",
        lambda self: ("project", home, project),
    )
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("mcp")
        await pilot.pause()
        grid = app.query_one("#mcp-grid", McpGrid)
        grid.set_scope("project")
        grid.set_rows([McpRow(slug="ctx7", source="npx", pin=None,
                              state="installed", cells={})])
        grid.restore_pending({("project", "standard", "ctx7"): "link"})
        await pilot.pause()
        app._apply_mcp_pending()
        await pilot.pause()
    lock = read_lock(lock_path_for_scope("project", home=home, project=project))
    assert sorted(e.harness for e in lock["ctx7"]) == ["standard"]  # collapsed
    mcp_json = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
    assert "ctx7" in mcp_json["mcpServers"]
