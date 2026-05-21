"""Tests for the Pi tab u/p toggle bindings.

Two surfaces:
1. CLIRunner.pi_load / pi_unload shell-out shape (subprocess mocked).
2. PiTabScreen press-u happy path (Pilot, runner mocked).
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from agent_toolkit_tui.runner import CLIRunner, RunnerError


# --- runner shell-out shape -------------------------------------------------

def _make_runner(tmp_path: Path) -> CLIRunner:
    return CLIRunner(toolkit_root=tmp_path, cli_path=Path("agent-toolkit-cli"))


def test_pi_load_invokes_cli_with_scope_and_toolkit_repo(monkeypatch, tmp_path):
    captured: dict[str, Any] = {}

    def fake_run(cmd, capture_output, text, check):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = _make_runner(tmp_path)
    runner.pi_load("status-bar", "user")

    assert captured["cmd"][1:] == [
        "pi", "load", "status-bar",
        "--scope", "user",
        "--toolkit-repo", str(tmp_path),
    ]


def test_pi_unload_invokes_cli_with_scope_and_toolkit_repo(monkeypatch, tmp_path):
    captured: dict[str, Any] = {}

    def fake_run(cmd, capture_output, text, check):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = _make_runner(tmp_path)
    runner.pi_unload("status-bar", "project")

    assert captured["cmd"][1:] == [
        "pi", "unload", "status-bar",
        "--scope", "project",
        "--toolkit-repo", str(tmp_path),
    ]


def test_pi_load_nonzero_exit_raises_runner_error(monkeypatch, tmp_path):
    def fake_run(cmd, capture_output, text, check):
        return subprocess.CompletedProcess(
            cmd, returncode=2, stdout="", stderr="boom: missing slug\n"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = _make_runner(tmp_path)
    with pytest.raises(RunnerError) as excinfo:
        runner.pi_load("nope", "user")
    assert "boom: missing slug" in str(excinfo.value)


# --- PiTabScreen Pilot ------------------------------------------------------

@pytest.mark.asyncio
async def test_pressing_u_loads_under_user_scope_and_refreshes(monkeypatch, tmp_path):
    # PiTab is part of the legacy multi-kind interface; not exposed in v2 default.
    monkeypatch.setenv("AGENT_TOOLKIT_TUI_LEGACY", "1")
    from agent_toolkit_tui.app import TUIApp
    from agent_toolkit_tui.runner import CLIRunner

    # Two inventory snapshots: before and after the user-scope load.
    record_before = {
        "slug": "status-bar",
        "origin": "first-party",
        "source": "extension:status-bar",
        "user_loaded": False,
        "project_loaded": False,
        "toolkit_intent": "user",
    }
    record_after = dict(record_before, user_loaded=True)

    inventories = iter([[record_before], [record_after]])

    load_calls: list[tuple[str, str]] = []

    def fake_pi_inventory(self):
        return next(inventories)

    def fake_pi_load(self, slug, scope):
        load_calls.append((slug, scope))

    monkeypatch.setattr(CLIRunner, "pi_inventory", fake_pi_inventory)
    monkeypatch.setattr(CLIRunner, "pi_load", fake_pi_load)
    # Minimal list_state stub so TUIApp.__init__ doesn't fail.
    monkeypatch.setattr(
        CLIRunner, "list_state",
        lambda self: {"assets": [], "links": {"user": {}, "project": {}}},
    )

    app = TUIApp(toolkit_root=tmp_path)
    async with app.run_test() as pilot:
        # Open the Pi modal.
        await pilot.press("8")
        await pilot.pause()
        # Highlight row 0 is the default cursor position; press u.
        await pilot.press("u")
        await pilot.pause()

        assert load_calls == [("status-bar", "user")]

        # The table should now show ✓ in the U column for the only row.
        from textual.widgets import DataTable
        table = app.screen.query_one("#pi-tab-table", DataTable)
        row = table.get_row_at(0)
        # Column order: Slug, Origin, U, P, Intent, Source.
        assert row[0] == "status-bar"
        assert row[2] == "✓"
