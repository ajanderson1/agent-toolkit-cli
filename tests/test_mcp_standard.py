"""Tests for the MCP standard projection: covered set, adapter, normalization, collapse."""
from __future__ import annotations

import json

import click
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


def test_collapse_covered_drops_covered_rows_for_slug():
    from agent_toolkit_cli.mcp_lock import McpLockEntry, collapse_covered
    lock = {
        "context7": [
            McpLockEntry("context7", "standard", "npx", "9.9.9"),
            McpLockEntry("context7", "claude-code", "npx", "9.9.9"),
            McpLockEntry("context7", "pi", "npx", "9.9.9"),
            McpLockEntry("context7", "codex", "npx", "9.9.9"),
        ],
        "other": [McpLockEntry("other", "claude-code", "npx", None)],
    }
    out = collapse_covered(lock, "context7", frozenset({"claude-code", "pi"}))
    harnesses = sorted(e.harness for e in out["context7"])
    assert harnesses == ["codex", "standard"]          # claude-code + pi dropped
    assert {e.harness for e in out["other"]} == {"claude-code"}  # other slug untouched


def test_collapse_covered_is_noop_when_no_covered_rows():
    from agent_toolkit_cli.mcp_lock import McpLockEntry, collapse_covered
    lock = {"context7": [McpLockEntry("context7", "standard", "npx", None)]}
    out = collapse_covered(lock, "context7", frozenset({"claude-code", "pi"}))
    assert [e.harness for e in out["context7"]] == ["standard"]


def test_normalize_project_collapses_claude_and_pi():
    from agent_toolkit_cli.commands.mcp._common import normalize_harness_tokens
    out = normalize_harness_tokens(("claude-code", "pi"), scope="project")
    assert out == ("standard",)  # both → standard, deduped


def test_normalize_project_keeps_outliers_and_order():
    from agent_toolkit_cli.commands.mcp._common import normalize_harness_tokens
    out = normalize_harness_tokens(("claude-code", "codex", "opencode"), scope="project")
    assert out == ("standard", "codex", "opencode")


def test_normalize_project_standard_token_passes_through():
    from agent_toolkit_cli.commands.mcp._common import normalize_harness_tokens
    assert normalize_harness_tokens(("standard",), scope="project") == ("standard",)


def test_normalize_global_does_not_normalize_claude_or_pi():
    from agent_toolkit_cli.commands.mcp._common import normalize_harness_tokens
    out = normalize_harness_tokens(("claude-code", "pi"), scope="global")
    assert out == ("claude-code", "pi")  # NO normalization at global scope


def test_normalize_global_rejects_standard_token():
    from agent_toolkit_cli.commands.mcp._common import normalize_harness_tokens
    with pytest.raises(click.UsageError, match="standard.*project"):
        normalize_harness_tokens(("standard",), scope="global")


def test_default_harnesses_project_is_standard_codex_opencode():
    from agent_toolkit_cli.commands.mcp._common import default_harnesses
    assert default_harnesses("project") == ("standard", "codex", "opencode")


def test_default_harnesses_global_is_the_concrete_four():
    from agent_toolkit_cli.commands.mcp._common import default_harnesses
    assert default_harnesses("global") == ("claude-code", "codex", "opencode", "pi")
