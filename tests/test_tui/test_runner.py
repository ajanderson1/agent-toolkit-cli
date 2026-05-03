"""Unit tests for runner.py — the only module that shells out."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_toolkit_tui.runner import CLIRunner, RunnerError


def test_runner_list_state_invokes_correct_args(tmp_path: Path):
    runner = CLIRunner(toolkit_root=tmp_path, cli_path=Path("/fake/agent-toolkit"))
    fake_proc = MagicMock(returncode=0, stdout='{"toolkit_root":"/x","harnesses":[],"assets":[]}', stderr="")
    with patch("agent_toolkit_tui.runner.subprocess.run", return_value=fake_proc) as mock:
        out = runner.list_state()
    args = mock.call_args.args[0]
    assert args == [str(Path("/fake/agent-toolkit")), "list", "--format=json", "--toolkit-repo", str(tmp_path.resolve())]
    assert out == {"toolkit_root": "/x", "harnesses": [], "assets": []}


def test_runner_list_state_raises_on_nonzero(tmp_path: Path):
    runner = CLIRunner(toolkit_root=tmp_path)
    fake_proc = MagicMock(returncode=2, stdout="", stderr="bad flag")
    with patch("agent_toolkit_tui.runner.subprocess.run", return_value=fake_proc):
        with pytest.raises(RunnerError) as excinfo:
            runner.list_state()
    assert "bad flag" in str(excinfo.value)


def test_runner_link_plan_pipes_stdin(tmp_path: Path):
    runner = CLIRunner(toolkit_root=tmp_path)
    fake_proc = MagicMock(returncode=0, stdout="", stderr="Plan applied: 2 ok, 0 failed (of 2 entries).")
    with patch("agent_toolkit_tui.runner.subprocess.run", return_value=fake_proc) as mock:
        result = runner.link_plan(scope="user", harness="claude",
                                  entries=[("skill", "alpha"), ("skill", "beta")])
    args, kwargs = mock.call_args
    assert "link" in args[0] and "user" in args[0] and "claude" in args[0]
    assert "--plan" in args[0] and "-" in args[0]
    assert kwargs["input"] == "skill:alpha\nskill:beta\n"
    assert result.ok == 2 and result.failed == 0


def test_runner_link_plan_partial_failure_returncode_1(tmp_path: Path):
    runner = CLIRunner(toolkit_root=tmp_path)
    fake_proc = MagicMock(returncode=1, stdout="",
                          stderr="failed: skill:does-not-exist\nPlan applied: 1 ok, 1 failed (of 2 entries).")
    with patch("agent_toolkit_tui.runner.subprocess.run", return_value=fake_proc):
        result = runner.link_plan(scope="user", harness="claude",
                                  entries=[("skill", "alpha"), ("skill", "does-not-exist")])
    assert result.ok == 1 and result.failed == 1
    assert "does-not-exist" in result.errors[0]


def test_runner_rc2_carries_parsed_errors(tmp_path: Path):
    """RunnerError raised on rc=2 must preserve parsed error lines."""
    runner = CLIRunner(toolkit_root=tmp_path)
    stderr = "failed: skill:bad-slug\nPlan applied: 0 ok, 1 failed (of 1 entries)."
    fake_proc = MagicMock(returncode=2, stdout="", stderr=stderr)
    with patch("agent_toolkit_tui.runner.subprocess.run", return_value=fake_proc):
        with pytest.raises(RunnerError) as excinfo:
            runner.link_plan(scope="user", harness="claude",
                             entries=[("skill", "bad-slug")])
    err = excinfo.value
    assert "rc=2" in str(err)
    assert len(err.errors) >= 1
    assert any("bad-slug" in e for e in err.errors)
