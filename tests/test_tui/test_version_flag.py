"""Regression: `agent-toolkit-tui --version` / `-V` prints and exits, no TUI."""
from __future__ import annotations

import re
import subprocess
import sys

import pytest


VERSION_LINE = re.compile(r"^agent-toolkit-tui, version \S+\n$")


@pytest.mark.parametrize("flag", ["--version", "-V"])
def test_version_flag_prints_and_exits(flag: str) -> None:
    result = subprocess.run(
        ["agent-toolkit-tui", flag],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert VERSION_LINE.match(result.stdout), repr(result.stdout)


def test_main_runs_tui_when_no_version_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """No version flag → main() must call TUIApp.run, not short-circuit."""
    from agent_toolkit_tui import app as tui_app

    monkeypatch.setattr(sys, "argv", ["agent-toolkit-tui"])
    called: dict[str, bool] = {"run": False}

    def _fake_run(self: tui_app.TUIApp) -> None:
        called["run"] = True

    monkeypatch.setattr(tui_app.TUIApp, "run", _fake_run)

    rc = tui_app.main()
    assert rc == 0
    assert called["run"] is True
