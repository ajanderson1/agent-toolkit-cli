"""Refresh does not scan its active catalogue-aware inventory twice."""
from collections import Counter

import pytest

from agent_toolkit_tui.app import TUIApp


KINDS = ("instruction", "command", "skill", "agent", "mcp", "pi")


@pytest.mark.asyncio
@pytest.mark.parametrize("active", KINDS)
async def test_refresh_scans_each_required_kind_once_and_keeps_hidden_drafts(monkeypatch, tmp_path, active):
    monkeypatch.chdir(tmp_path)
    calls = Counter()
    for kind in KINDS:
        def refresh(self, _kind=kind, **kwargs):
            calls[_kind] += 1
        monkeypatch.setattr(TUIApp, f"_refresh_{kind}_view", refresh)

    app = TUIApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_asset_type("pi-extension" if active == "pi" else active)
        hidden = "command" if active != "command" else "agent"
        active_grid = app.query_one(f"#{active}-grid")
        hidden_grid = app.query_one(f"#{hidden}-grid")
        key = ("project", "draft") if active == "pi" else ("project", "standard", "draft")
        hidden_key = ("project", "standard", "hidden")
        active_grid.restore_pending({key: "link"})
        hidden_grid.restore_pending({hidden_key: "link"})
        calls.clear()
        app.action_refresh()
        assert not active_grid.pending_entries()
        assert hidden_grid.pending_entries() == {hidden_key: "link"}
        expected = Counter({kind: 1 for kind in ("skill", "command", "agent", "pi")})
        if active in ("instruction", "mcp"):
            expected[active] = 1
        assert calls == expected
