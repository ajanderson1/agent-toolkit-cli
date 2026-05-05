"""Claude adapter — ConfigFileAdapter against ~/.claude.json."""
from __future__ import annotations

from pathlib import Path

import pytest


def _make_entry(name: str = "context7", *, transport: str = "stdio",
                command: str = "npx", args: list[str] | None = None,
                env: dict[str, str] | None = None,
                url: str | None = None,
                headers: dict[str, str] | None = None):
    from agent_toolkit.harness_adapters.base import McpEntry

    inner: dict = {"command": command}
    if args is not None:
        inner["args"] = args
    if env is not None:
        inner["env"] = env

    spec: dict = {"transport": transport, "install_method": "npx"}
    if url is not None:
        spec["url"] = url
    if headers is not None:
        spec["headers"] = headers

    return McpEntry(
        name=name,
        inner_config=inner,
        mcp_spec=spec,
    )


def test_claude_adapter_basic_attrs():
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    a = ClaudeAdapter()
    assert a.name == "claude"
    assert a.strategy == "config_file"


def test_claude_user_config_target(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = ClaudeAdapter()
    assert a.config_target("user", tmp_path) == tmp_path / ".claude.json"


def test_claude_project_config_target_requires_file(tmp_path):
    """Project target only set when .mcp.json exists at project_root."""
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    proj = tmp_path / "p"
    proj.mkdir()
    a = ClaudeAdapter()
    # No .mcp.json → no target
    assert a.config_target("project", proj) is None
    # Create .mcp.json → target appears
    (proj / ".mcp.json").write_text("{}\n")
    assert a.config_target("project", proj) == proj / ".mcp.json"


def test_claude_can_install_accepts_all_transports():
    """Claude supports stdio/sse/http natively — adapter does not refuse any."""
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    a = ClaudeAdapter()
    a.can_install(_make_entry(transport="stdio"))  # no exception
    a.can_install(_make_entry(transport="sse", url="https://x"))  # no exception
    a.can_install(_make_entry(transport="http", url="https://x"))  # no exception


def test_claude_diff_creates_file_when_missing(monkeypatch, tmp_path):
    """No .claude.json on disk → one create-action with rendered bytes."""
    import json
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"], env={"TOK": "x"})

    actions = a.diff("user", tmp_path, [entry])
    assert len(actions) == 1
    act = actions[0]
    assert act.path == tmp_path / ".claude.json"
    assert act.op == "create"
    assert act.bytes_before is None
    assert act.bytes_after is not None

    parsed = json.loads(act.contents)
    assert "mcpServers" in parsed
    assert "context7" in parsed["mcpServers"]
    server = parsed["mcpServers"]["context7"]
    assert server["type"] == "stdio"
    assert server["command"] == "npx"
    assert server["args"] == ["-y", "@upstash/context7-mcp"]
    assert server["env"] == {"TOK": "x"}


def test_claude_diff_preserves_other_top_level_keys(monkeypatch, tmp_path):
    """Adding an MCP to a .claude.json with other settings yields one update;
    the other top-level keys (theme, numStartups) survive."""
    import json
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    target.write_text(json.dumps({
        "theme": "dark",
        "numStartups": 12,
    }, indent=2, sort_keys=True))
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    actions = a.diff("user", tmp_path, [entry])
    assert len(actions) == 1
    act = actions[0]
    assert act.op == "update"
    parsed = json.loads(act.contents)
    assert parsed["theme"] == "dark"
    assert parsed["numStartups"] == 12
    assert "context7" in parsed["mcpServers"]


def test_claude_diff_unchanged_when_aligned(monkeypatch, tmp_path):
    """If on-disk already matches the desired render, diff returns []."""
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    actions2 = a.diff("user", tmp_path, [entry])
    assert actions2 == []
