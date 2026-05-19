"""Gemini adapter — ConfigFileAdapter against ~/.gemini/settings.json."""
from __future__ import annotations

import json


def _make_entry(name: str = "context7", *, transport: str = "stdio",
                command: str = "npx", args: list[str] | None = None,
                env: dict[str, str] | None = None,
                url: str | None = None,
                headers: dict[str, str] | None = None):
    from agent_toolkit_cli.harness_adapters.base import McpEntry

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

    return McpEntry(name=name, inner_config=inner, mcp_spec=spec)


def test_gemini_adapter_basic_attrs():
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    a = GeminiAdapter()
    assert a.name == "gemini"
    assert a.strategy == "config_file"


def test_gemini_user_config_target(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = GeminiAdapter()
    assert a.config_target("user", tmp_path) == tmp_path / ".gemini" / "settings.json"


def test_gemini_project_config_target_requires_dir(tmp_path):
    """Project target only set when .gemini/ exists in project_root."""
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    proj = tmp_path / "p"
    proj.mkdir()
    a = GeminiAdapter()
    assert a.config_target("project", proj) is None
    (proj / ".gemini").mkdir()
    assert a.config_target("project", proj) == proj / ".gemini" / "settings.json"


def test_gemini_can_install_accepts_all_transports():
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    a = GeminiAdapter()
    a.can_install(_make_entry(transport="stdio"))
    a.can_install(_make_entry(transport="http", url="https://x"))
    a.can_install(_make_entry(transport="sse", url="https://x"))


def test_gemini_diff_creates_file_when_missing(monkeypatch, tmp_path):
    """stdio entry → settings.json with top-level mcpServers.<name>."""
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = GeminiAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"], env={"TOK": "x"})

    [act] = a.diff("user", tmp_path, [entry])
    assert act.op == "create"
    assert act.path == tmp_path / ".gemini" / "settings.json"
    parsed = json.loads(act.contents)
    assert "mcpServers" in parsed
    server = parsed["mcpServers"]["context7"]
    assert server["type"] == "stdio"
    assert server["command"] == "npx"
    assert server["args"] == ["-y", "@upstash/context7-mcp"]
    assert server["env"] == {"TOK": "x"}


def test_gemini_diff_remote_shape_for_http(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = GeminiAdapter()
    entry = _make_entry(transport="http", url="https://example/mcp",
                        headers={"Authorization": "Bearer x"})
    [act] = a.diff("user", tmp_path, [entry])
    parsed = json.loads(act.contents)
    server = parsed["mcpServers"]["context7"]
    assert server["type"] == "http"
    assert server["url"] == "https://example/mcp"
    assert server["headers"] == {"Authorization": "Bearer x"}


def test_gemini_list_installed_round_trips(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".gemini" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"mcpServers": {"a": {}, "b": {}}}))
    a = GeminiAdapter()
    assert a.list_installed("user", tmp_path) == {"a", "b"}


def test_gemini_entry_drift_detects_change(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = GeminiAdapter()
    entry = _make_entry()

    # Pre-write a divergent on-disk entry
    settings = tmp_path / ".gemini" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"mcpServers": {"context7": {"type": "stdio",
                                                                "command": "DIFFERENT"}}}))
    assert a.entry_drift("user", tmp_path, entry) is True


def test_gemini_missing_file_returns_empty(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = GeminiAdapter()
    assert a.list_installed("user", tmp_path) == set()
    assert a.entry_drift("user", tmp_path, _make_entry()) is False


def test_gemini_get_adapter_returns_real_adapter():
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter
    from agent_toolkit_cli.harness_adapters.gemini import GeminiAdapter

    a = get_adapter("gemini", "mcp")
    assert isinstance(a, GeminiAdapter)
    assert not isinstance(a, UnimplementedAdapter)
