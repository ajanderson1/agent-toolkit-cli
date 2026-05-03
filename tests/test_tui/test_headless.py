"""Tests for `agent-toolkit-tui --headless --plan ...` mode."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_toolkit_tui.app import _read_plan, main


def test_read_plan_skips_comments_and_blanks(tmp_path: Path):
    plan = tmp_path / "p.txt"
    plan.write_text(
        "# comment\n"
        "\n"
        "skill:alpha\n"
        "agent:builder   # inline\n"
    )
    out = _read_plan(plan)
    assert out == [("skill", "alpha"), ("agent", "builder")]


def test_main_headless_dry_run_returns_zero(tmp_path: Path, monkeypatch):
    plan = tmp_path / "p.txt"
    plan.write_text("skill:alpha\n")
    fake_argv = ["prog", "--headless", "--toolkit-repo", str(tmp_path),
                 "--plan", str(plan), "--scope", "user", "--harness", "claude"]
    monkeypatch.setattr("sys.argv", fake_argv)
    # Patch the runner so we don't actually shell out
    from agent_toolkit_tui import app as app_mod
    from agent_toolkit_tui.runner import PlanResult

    class FakeRunner:
        def __init__(self, *a, **k): pass
        def link_plan(self, **kw):
            assert kw["entries"] == [("skill", "alpha")]
            assert kw["dry_run"] is True
            return PlanResult(ok=1, failed=0)

    monkeypatch.setattr(app_mod, "CLIRunner", FakeRunner)
    rc = main()
    assert rc == 0
