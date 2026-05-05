"""OpenCode adapter — ConfigFileAdapter against ~/.config/opencode/opencode.json."""
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


def test_opencode_adapter_basic_attrs():
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    a = OpenCodeAdapter()
    assert a.name == "opencode"
    assert a.strategy == "config_file"


def test_opencode_user_config_target(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = OpenCodeAdapter()
    assert a.config_target("user", tmp_path) == (
        tmp_path / ".config" / "opencode" / "opencode.json"
    )


def test_opencode_project_config_target_requires_dir(tmp_path):
    """Project target only set when .opencode/ exists in project_root."""
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    proj = tmp_path / "p"
    proj.mkdir()
    a = OpenCodeAdapter()
    assert a.config_target("project", proj) is None
    (proj / ".opencode").mkdir()
    assert a.config_target("project", proj) == (
        proj / ".opencode" / "opencode.json"
    )


def test_opencode_can_install_accepts_all_transports():
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    a = OpenCodeAdapter()
    a.can_install(_make_entry(transport="stdio"))
    a.can_install(_make_entry(transport="http", url="https://x"))
    a.can_install(_make_entry(transport="sse", url="https://x"))


def test_opencode_diff_creates_file_when_missing_local_shape(monkeypatch, tmp_path):
    """stdio entry → on-disk {type: 'local', command: [str, ...], environment, enabled}."""
    import json
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"], env={"TOK": "x"})

    [act] = a.diff("user", tmp_path, [entry])
    assert act.op == "create"
    assert act.path == tmp_path / ".config" / "opencode" / "opencode.json"
    parsed = json.loads(act.contents)
    assert "mcp" in parsed
    server = parsed["mcp"]["context7"]
    assert server["type"] == "local"
    assert server["command"] == ["npx", "-y", "@upstash/context7-mcp"]
    assert server["environment"] == {"TOK": "x"}
    assert server["enabled"] is True


def test_opencode_diff_remote_shape_for_http(monkeypatch, tmp_path):
    import json
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = OpenCodeAdapter()
    entry = _make_entry(name="remote-mcp", transport="http",
                        url="https://example.com/mcp",
                        headers={"X-Token": "abc"})

    [act] = a.diff("user", tmp_path, [entry])
    parsed = json.loads(act.contents)
    server = parsed["mcp"]["remote-mcp"]
    assert server["type"] == "remote"
    assert server["url"] == "https://example.com/mcp"
    assert server["headers"] == {"X-Token": "abc"}
    assert server["enabled"] is True


def test_opencode_diff_preserves_other_top_level_keys(monkeypatch, tmp_path):
    """theme/model/etc at top level survive link/unlink."""
    import json
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({
        "theme": "tokyonight",
        "model": "anthropic/claude-sonnet-4",
    }, indent=2, sort_keys=True) + "\n")

    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [act] = a.diff("user", tmp_path, [entry])
    parsed = json.loads(act.contents)
    assert parsed["theme"] == "tokyonight"
    assert parsed["model"] == "anthropic/claude-sonnet-4"
    assert "context7" in parsed["mcp"]


def test_opencode_diff_unchanged_when_aligned(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)
    assert a.diff("user", tmp_path, [entry]) == []


def test_opencode_unlink_removes_managed_entry(monkeypatch, tmp_path):
    import json
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [link_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(link_act.contents)

    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    parsed = json.loads(actions[0].contents)
    assert "context7" not in parsed.get("mcp", {})


def test_opencode_unlink_does_not_touch_handrolled_entries(monkeypatch, tmp_path):
    import json
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({
        "mcp": {
            "preexisting": {"type": "local", "command": ["node", "./local-mcp.js"],
                            "enabled": True},
        },
        "theme": "tokyonight",
    }, indent=2, sort_keys=True) + "\n")
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [link_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(link_act.contents)

    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    parsed = json.loads(actions[0].contents)
    assert "context7" not in parsed.get("mcp", {})
    assert "preexisting" in parsed["mcp"]
    assert parsed["theme"] == "tokyonight"


def test_opencode_link_unlink_round_trip_idempotent(monkeypatch, tmp_path):
    import json
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    src_doc = {
        "mcp": {
            "preexisting": {"type": "local", "command": ["node", "./local-mcp.js"],
                            "enabled": True},
        },
        "theme": "tokyonight",
        "model": "anthropic/claude-sonnet-4",
    }
    target.write_text(json.dumps(src_doc, indent=2, sort_keys=True) + "\n")

    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)
    [act2] = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    target.write_bytes(act2.contents)

    after = json.loads(target.read_bytes())
    assert after == src_doc


def test_opencode_list_installed_returns_all_mcp_names(monkeypatch, tmp_path):
    import json
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({
        "mcp": {
            "context7": {"type": "local", "command": ["npx"], "enabled": True},
            "preexisting": {"type": "local", "command": ["node"], "enabled": True},
        }
    }, indent=2, sort_keys=True) + "\n")
    a = OpenCodeAdapter()
    assert a.list_installed("user", tmp_path) == {"context7", "preexisting"}


def test_opencode_list_installed_missing_file_returns_empty(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = OpenCodeAdapter()
    assert a.list_installed("user", tmp_path) == set()


def test_opencode_entry_drift_false_when_aligned(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)
    assert a.entry_drift("user", tmp_path, entry) is False


def test_opencode_entry_drift_true_after_hand_edit(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    text = target.read_text().replace('"enabled": true', '"enabled": false')
    target.write_text(text)
    assert a.entry_drift("user", tmp_path, entry) is True


def test_opencode_re_link_is_no_op_when_aligned(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.opencode import OpenCodeAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".config" / "opencode" / "opencode.json"
    target.parent.mkdir(parents=True)
    a = OpenCodeAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [first] = a.diff("user", tmp_path, [entry])
    target.write_bytes(first.contents)
    assert a.diff("user", tmp_path, [entry], previously_allowed={"context7"}) == []
