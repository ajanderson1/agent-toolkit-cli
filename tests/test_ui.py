import os

import pytest

from agent_toolkit_cli._ui import header, summary


def test_header_writes_to_stderr(capsys):
    header("hello")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "hello" in captured.err


def test_summary_writes_to_stderr(capsys):
    summary("done")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "done" in captured.err


def test_quiet_env_suppresses_header(capsys, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_QUIET", "1")
    header("hello")
    captured = capsys.readouterr()
    assert captured.err == ""


def test_quiet_env_suppresses_summary(capsys, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_QUIET", "1")
    summary("done")
    captured = capsys.readouterr()
    assert captured.err == ""
