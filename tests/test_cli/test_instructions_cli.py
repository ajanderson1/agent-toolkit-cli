"""CLI surface: `agent-toolkit-cli instructions <verb>` smoke."""
from __future__ import annotations

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_instructions_group_registered():
    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "--help"])
    assert result.exit_code == 0, result.output
    assert "install" in result.output
    assert "uninstall" in result.output
    assert "list" in result.output
    assert "status" in result.output
    assert "doctor" in result.output
