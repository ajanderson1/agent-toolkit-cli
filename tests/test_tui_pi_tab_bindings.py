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
