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
