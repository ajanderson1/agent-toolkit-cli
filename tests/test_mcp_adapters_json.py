"""Tests for the MCP adapter base + JSON-family adapter."""
from __future__ import annotations

import json

import pytest

from agent_toolkit_cli.mcp_adapters import (
    UnsupportedMcpHarnessError,
    atomic_write_text,
    get_adapter,
)


def test_get_adapter_dispatches_known_harnesses():
    for harness in ("claude-code", "codex", "opencode", "pi"):
        adapter = get_adapter(harness)
        assert adapter.name == harness


def test_get_adapter_unknown_harness_raises():
    with pytest.raises(UnsupportedMcpHarnessError):
        get_adapter("emacs")


def test_atomic_write_text_replaces_in_place(tmp_path):
    target = tmp_path / "config.json"
    target.write_text('{"old": true}')
    atomic_write_text(target, '{"new": true}')
    assert json.loads(target.read_text()) == {"new": True}
    # No temp files left behind
    leftovers = [p for p in tmp_path.iterdir() if p.name != "config.json"]
    assert leftovers == []


def test_atomic_write_text_creates_parent_dirs(tmp_path):
    target = tmp_path / "nested" / "deep" / "config.json"
    atomic_write_text(target, "{}")
    assert target.read_text() == "{}"
