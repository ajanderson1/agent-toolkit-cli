"""Tests for the MCP standard projection: covered set, adapter, normalization, collapse."""
from __future__ import annotations

import json

import pytest


def test_standard_covered_project_is_claude_and_pi():
    from agent_toolkit_cli.mcp_standard import mcp_standard_covered
    assert mcp_standard_covered("project") == frozenset({"claude-code", "pi"})


def test_standard_covered_unknown_scope_raises():
    from agent_toolkit_cli.mcp_standard import mcp_standard_covered
    with pytest.raises(KeyError):
        mcp_standard_covered("global")


def _inner():
    return {"type": "stdio", "command": "npx", "args": ["-y", "ctx7"]}


def test_standard_adapter_writes_shared_mcp_json(tmp_path):
    from agent_toolkit_cli.mcp_adapters import get_adapter
    project = tmp_path / "proj"
    project.mkdir()
    written = get_adapter("standard").install(
        "context7", _inner(), scope="project", home=tmp_path, project=project,
    )
    assert written == project / ".mcp.json"
    doc = json.loads(written.read_text())
    assert doc["mcpServers"]["context7"] == _inner()


def test_standard_adapter_preserves_siblings_and_is_idempotent(tmp_path):
    from agent_toolkit_cli.mcp_adapters import get_adapter
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"keep": {"command": "x"}}}, indent=2) + "\n"
    )
    adapter = get_adapter("standard")
    adapter.install("context7", _inner(), scope="project", home=tmp_path, project=project)
    first = (project / ".mcp.json").read_text()
    adapter.install("context7", _inner(), scope="project", home=tmp_path, project=project)
    assert (project / ".mcp.json").read_text() == first  # idempotent
    doc = json.loads(first)
    assert doc["mcpServers"]["keep"] == {"command": "x"}   # sibling preserved
    assert doc["mcpServers"]["context7"] == _inner()


def test_standard_adapter_global_target_raises(tmp_path):
    """No global standard exists — a global config_target must fail loud."""
    from agent_toolkit_cli.mcp_adapters import get_adapter
    with pytest.raises(ValueError, match="no global target"):
        get_adapter("standard").config_target(scope="global", home=tmp_path, project=None)
