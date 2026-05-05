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


def test_claude_unlink_removes_managed_entry_via_previously_allowed(monkeypatch, tmp_path):
    """unlink semantics: entries=[], previously_allowed={'context7'} → removes context7."""
    import json
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [link_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(link_act.contents)
    assert "context7" in json.loads(target.read_bytes())["mcpServers"]

    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    assert len(actions) == 1
    act = actions[0]
    assert act.op == "update"
    parsed = json.loads(act.contents)
    assert "mcpServers" not in parsed or "context7" not in parsed.get("mcpServers", {})


def test_claude_unlink_does_not_touch_handrolled_entries(monkeypatch, tmp_path):
    """Names not in previously_allowed | desired are hand-rolled — preserved."""
    import json
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    target.write_text(json.dumps({
        "mcpServers": {
            "preexisting": {"type": "stdio", "command": "node",
                            "args": ["./local-mcp.js"]}
        },
        "theme": "dark",
    }, indent=2, sort_keys=True) + "\n")
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [link_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(link_act.contents)
    after_link = json.loads(target.read_bytes())
    assert "context7" in after_link["mcpServers"]
    assert "preexisting" in after_link["mcpServers"]
    assert after_link["theme"] == "dark"

    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    assert len(actions) == 1
    parsed = json.loads(actions[0].contents)
    assert "context7" not in parsed.get("mcpServers", {})
    assert "preexisting" in parsed["mcpServers"]
    assert parsed["theme"] == "dark"


def test_claude_link_unlink_round_trip_idempotent(monkeypatch, tmp_path):
    """Source with hand-rolled entry → link unrelated MCP → unlink → structurally equal."""
    import json
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    src_doc = {
        "mcpServers": {
            "preexisting": {"type": "stdio", "command": "node",
                            "args": ["./local-mcp.js"]}
        },
        "theme": "dark",
        "numStartups": 7,
    }
    target.write_text(json.dumps(src_doc, indent=2, sort_keys=True) + "\n")

    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    assert len(actions) == 1
    target.write_bytes(actions[0].contents)

    after = json.loads(target.read_bytes())
    assert after == src_doc, (
        f"Round-trip is not structurally equal.\n"
        f"src={src_doc}\nafter={after}"
    )


def test_claude_list_installed_returns_all_mcp_server_names(monkeypatch, tmp_path):
    import json
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    target.write_text(json.dumps({
        "mcpServers": {
            "context7": {"type": "stdio", "command": "npx"},
            "preexisting": {"type": "stdio", "command": "node"},
        }
    }, indent=2, sort_keys=True) + "\n")
    a = ClaudeAdapter()
    assert a.list_installed("user", tmp_path) == {"context7", "preexisting"}


def test_claude_list_installed_missing_file_returns_empty(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = ClaudeAdapter()
    assert a.list_installed("user", tmp_path) == set()


def test_claude_entry_drift_false_when_aligned(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    assert a.entry_drift("user", tmp_path, entry) is False


def test_claude_entry_drift_true_after_hand_edit(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    text = target.read_text().replace(
        '"@upstash/context7-mcp"', '"@upstash/context7-mcp", "--debug"'
    )
    target.write_text(text)
    assert a.entry_drift("user", tmp_path, entry) is True


def test_claude_re_link_byte_identical_when_already_linked(monkeypatch, tmp_path):
    """AC #2 analogue: re-running link with same allow-list yields no write."""
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude.json"
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [first] = a.diff("user", tmp_path, [entry])
    target.write_bytes(first.contents)
    actions = a.diff("user", tmp_path, [entry], previously_allowed={"context7"})
    assert actions == []


def test_claude_diff_handles_http_transport(monkeypatch, tmp_path):
    import json
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = ClaudeAdapter()
    entry = _make_entry(
        name="remote-mcp", transport="http",
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer xyz"},
    )
    [act] = a.diff("user", tmp_path, [entry])
    parsed = json.loads(act.contents)
    server = parsed["mcpServers"]["remote-mcp"]
    assert server["type"] == "http"
    assert server["url"] == "https://example.com/mcp"
    assert server["headers"] == {"Authorization": "Bearer xyz"}
    # No stdio fields present
    assert "command" not in server
    assert "args" not in server


def test_claude_diff_handles_sse_transport(monkeypatch, tmp_path):
    import json
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = ClaudeAdapter()
    entry = _make_entry(name="sse-mcp", transport="sse",
                        url="https://example.com/sse")
    [act] = a.diff("user", tmp_path, [entry])
    parsed = json.loads(act.contents)
    server = parsed["mcpServers"]["sse-mcp"]
    assert server["type"] == "sse"
    assert server["url"] == "https://example.com/sse"


def test_claude_can_install_refuses_remote_without_url():
    """spec.transport=http with no spec.url → CannotInstall."""
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter
    from agent_toolkit.harness_adapters.base import CannotInstall

    a = ClaudeAdapter()
    # can_install accepts everything — the refusal lives in _build_entry_dict,
    # surfaced via diff() at render time.
    entry = _make_entry(name="bad", transport="http")  # no url
    a.can_install(entry)  # passes
    with pytest.raises(CannotInstall, match="url"):
        a.diff("user", Path("/tmp"), [entry])


def test_claude_project_scope_round_trip(tmp_path):
    """Project-scope mutation against `<proj>/.mcp.json`."""
    import json
    from agent_toolkit.harness_adapters.claude import ClaudeAdapter

    proj = tmp_path / "p"
    proj.mkdir()
    (proj / ".mcp.json").write_text("{}\n")
    a = ClaudeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [act] = a.diff("project", proj, [entry])
    assert act.path == proj / ".mcp.json"
    assert act.op == "update"
    parsed = json.loads(act.contents)
    assert "context7" in parsed["mcpServers"]
