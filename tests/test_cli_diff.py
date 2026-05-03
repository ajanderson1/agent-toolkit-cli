"""Pytest port of tests/bats/test_diff.bats. Each test cites the bats file:line it replaces."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit.cli import main


def test_diff_shows_would_link(env, seed_skill):
    """Replaces tests/bats/test_diff.bats:40-44."""
    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude").mkdir()
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "diff", "user", "claude"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "would-link" in result.output


def test_diff_previewing_header(env, seed_skill):
    """Replaces tests/bats/test_diff.bats:46-50."""
    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "diff", "user", "claude"])
    assert result.exit_code == 0
    assert "Previewing" in result.stderr


# Issue #9 — diff inherits link's harness validation via ctx.invoke
def test_diff_unknown_harness_exits_2(env):
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(env["toolkit_root"]), "diff", "user", "banana"],
    )
    assert result.exit_code == 2
    assert "unknown harness 'banana'" in result.stderr
