"""Tests for doctor's harness_homes group (issue #13)."""
from __future__ import annotations

import pytest

from agent_toolkit_cli.doctor import harness_homes
from agent_toolkit_cli.doctor.result import Status


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    return h


def test_all_present_returns_ok(home):
    for d in (".claude", ".codex", ".config/opencode", ".pi"):
        (home / d).mkdir(parents=True)
    result = harness_homes.run()
    assert result.status == Status.OK
    assert result.name == "harness-homes"


def test_one_missing_returns_warn(home):
    # codex deliberately not created
    for d in (".claude", ".config/opencode", ".pi"):
        (home / d).mkdir(parents=True)
    result = harness_homes.run()
    assert result.status == Status.WARN
    assert any("codex" in f and "not present" in f for f in result.findings)


def test_all_missing_returns_warn(home):
    result = harness_homes.run()
    assert result.status == Status.WARN
    for h in ("claude", "codex", "opencode", "pi"):
        assert any(h in f and "not present" in f for f in result.findings)
