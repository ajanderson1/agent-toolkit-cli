"""Unit tests for runner.py — the only module that shells out."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_toolkit_tui.runner import CLIRunner, RunnerError, _locate_cli


def test_locate_cli_uses_shutil_which(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """After the unification, runner.py must find the installed `agent-toolkit`
    via PATH, not by walking up to bin/agent-toolkit."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_cli = fake_bin / "agent-toolkit"
    fake_cli.write_text("#!/bin/sh\n")
    fake_cli.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin))
    monkeypatch.delenv("AGENT_TOOLKIT_CLI", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_BASH_CLI", raising=False)
    assert _locate_cli() == fake_cli


def test_locate_cli_env_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """$AGENT_TOOLKIT_CLI overrides PATH lookup."""
    fake = tmp_path / "fake-cli"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv("AGENT_TOOLKIT_CLI", str(fake))
    assert _locate_cli() == fake


def test_locate_cli_rejects_invalid_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENT_TOOLKIT_CLI", str(tmp_path / "missing"))
    with pytest.raises(FileNotFoundError):
        _locate_cli()


def test_locate_cli_raises_when_not_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """When agent-toolkit is not on PATH and no override is set, raise with an
    actionable hint."""
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.delenv("AGENT_TOOLKIT_CLI", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_BASH_CLI", raising=False)
    with pytest.raises(FileNotFoundError) as excinfo:
        _locate_cli()
    assert "agent-toolkit" in str(excinfo.value)


def test_runner_list_state_invokes_correct_args(tmp_path: Path):
    runner = CLIRunner(toolkit_root=tmp_path, cli_path=Path("/fake/agent-toolkit"))
    fake_proc = MagicMock(returncode=0, stdout='{"toolkit_root":"/x","harnesses":[],"assets":[]}', stderr="")
    with patch("agent_toolkit_tui.runner.subprocess.run", return_value=fake_proc) as mock:
        out = runner.list_state()
    args = mock.call_args.args[0]
    assert args == [str(Path("/fake/agent-toolkit")), "list", "--format=json", "--toolkit-repo", str(tmp_path.resolve())]
    assert out == {"toolkit_root": "/x", "harnesses": [], "assets": []}


def test_runner_list_state_raises_on_nonzero(tmp_path: Path):
    runner = CLIRunner(toolkit_root=tmp_path, cli_path=Path("/fake/agent-toolkit"))
    fake_proc = MagicMock(returncode=2, stdout="", stderr="bad flag")
    with patch("agent_toolkit_tui.runner.subprocess.run", return_value=fake_proc):
        with pytest.raises(RunnerError) as excinfo:
            runner.list_state()
    assert "bad flag" in str(excinfo.value)


def test_runner_link_plan_pipes_stdin(tmp_path: Path):
    runner = CLIRunner(toolkit_root=tmp_path, cli_path=Path("/fake/agent-toolkit"))
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
    runner = CLIRunner(toolkit_root=tmp_path, cli_path=Path("/fake/agent-toolkit"))
    fake_proc = MagicMock(returncode=1, stdout="",
                          stderr="failed: skill:does-not-exist\nPlan applied: 1 ok, 1 failed (of 2 entries).")
    with patch("agent_toolkit_tui.runner.subprocess.run", return_value=fake_proc):
        result = runner.link_plan(scope="user", harness="claude",
                                  entries=[("skill", "alpha"), ("skill", "does-not-exist")])
    assert result.ok == 1 and result.failed == 1
    assert "does-not-exist" in result.errors[0]


def test_runner_rc2_carries_parsed_errors(tmp_path: Path):
    """RunnerError raised on rc=2 must preserve parsed error lines."""
    runner = CLIRunner(toolkit_root=tmp_path, cli_path=Path("/fake/agent-toolkit"))
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
