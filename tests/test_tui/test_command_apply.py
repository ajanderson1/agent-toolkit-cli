"""TUI Apply for the Commands standard slot (#482)."""
from __future__ import annotations

import pytest

from agent_toolkit_cli.command_lock import LockEntry, LockFile, read_lock, write_lock
from agent_toolkit_tui.app import TUIApp
from agent_toolkit_tui.command_state import CommandRow
from agent_toolkit_tui.widgets.command_grid import CommandGrid


def _seed(home, text: str = "demo body\n") -> None:
    lib = home / ".agent-toolkit" / "commands" / "demo"
    lib.mkdir(parents=True)
    (lib / "COMMAND.md").write_text(text)
    write_lock(
        home / ".agent-toolkit" / "commands-lock.json",
        LockFile(
            version=1,
            skills={
                "demo": LockEntry(
                    source="o/r",
                    source_type="github",
                    ref="main",
                    command_path="COMMAND.md",
                )
            },
        ),
    )


@pytest.mark.asyncio
async def test_apply_standard_link_and_unlink(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _seed(home)
    monkeypatch.setattr(
        TUIApp,
        "_scope_to_roots",
        lambda self: ("global", home, None),
    )
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("command")
        await pilot.pause()
        grid = app.query_one("#command-grid", CommandGrid)
        grid.set_scope("global")
        grid.set_rows(
            [
                CommandRow(
                    slug="demo",
                    source="o/r",
                    ref="main",
                    state="library",
                    cells={},
                )
            ]
        )
        grid.restore_pending({("global", "standard", "demo"): "link"})
        await pilot.pause()
        app._apply_command_pending()
        await pilot.pause()

        dest = home / ".claude" / "commands" / "demo.md"
        assert dest.exists() or dest.is_symlink()
        lock = read_lock(home / ".agent-toolkit" / "commands-lock.json")
        assert "standard" in lock.skills["demo"].harnesses

        grid.restore_pending({("global", "standard", "demo"): "unlink"})
        await pilot.pause()
        app._apply_command_pending()
        await pilot.pause()

        assert not dest.exists() and not dest.is_symlink()
        lock = read_lock(home / ".agent-toolkit" / "commands-lock.json")
        assert "standard" not in lock.skills["demo"].harnesses


@pytest.mark.asyncio
async def test_apply_dispatch_routes_command(monkeypatch):
    routed = {"command": False, "agent": False}
    monkeypatch.setattr(
        TUIApp, "_apply_command_pending",
        lambda self: routed.__setitem__("command", True),
    )
    monkeypatch.setattr(
        TUIApp, "_apply_agent_pending",
        lambda self: routed.__setitem__("agent", True),
    )
    app = TUIApp()
    async with app.run_test() as pilot:
        app.action_asset_type("command")
        await pilot.pause()
        app.action_apply()
        await pilot.pause()
    assert routed["command"] is True and routed["agent"] is False
