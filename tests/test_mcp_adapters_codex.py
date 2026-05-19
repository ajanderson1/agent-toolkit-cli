"""Codex adapter — ConfigFileAdapter against ~/.codex/config.toml."""
from __future__ import annotations

from pathlib import Path

import pytest


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
    return McpEntry(
        name=name,
        inner_config=inner,
        mcp_spec=spec,
    )


def test_codex_adapter_basic_attrs():
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    a = CodexAdapter()
    assert a.name == "codex"
    assert a.strategy == "config_file"


def test_codex_user_config_target(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexAdapter()
    assert a.config_target("user", tmp_path) == tmp_path / ".codex" / "config.toml"


def test_codex_project_config_target_returns_path_unconditionally(tmp_path):
    """Project target is always `<project_root>/.codex/config.toml`, present or not.

    Regression test for #125 — previously returned None when `.codex/` absent,
    causing `link project codex mcp:<slug>` to silently no-op.
    """
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    proj = tmp_path / "p"
    proj.mkdir()
    a = CodexAdapter()
    # No .codex/ → path still returned
    assert a.config_target("project", proj) == proj / ".codex" / "config.toml"
    # With .codex/ → same path
    (proj / ".codex").mkdir()
    assert a.config_target("project", proj) == proj / ".codex" / "config.toml"


def test_codex_diff_project_creates_config_when_absent(tmp_path):
    """`link project codex` creates `.codex/config.toml` if missing. Regression for #125."""
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    proj = tmp_path / "p"
    proj.mkdir()
    entry = _make_entry(name="demo-mcp", command="/bin/true")
    a = CodexAdapter()
    actions = a.diff("project", proj, [entry])
    assert len(actions) == 1
    act = actions[0]
    assert act.op == "create"
    assert act.path == proj / ".codex" / "config.toml"
    text = act.contents.decode("utf-8")
    assert "[mcp_servers.demo-mcp]" in text or 'mcp_servers."demo-mcp"' in text


def test_codex_can_install_accepts_stdio():
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    a = CodexAdapter()
    a.can_install(_make_entry(transport="stdio"))  # no exception


def test_codex_can_install_accepts_http():
    """#74: http transport is now accepted (was previously refused)."""
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    a = CodexAdapter()
    a.can_install(_make_entry(transport="http", url="https://example/mcp"))  # no exception


def test_codex_can_install_refuses_sse():
    """SSE remains refused — deprecated upstream and Codex has no on-disk shape for it."""
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter
    from agent_toolkit_cli.harness_adapters.base import CannotInstall

    a = CodexAdapter()
    with pytest.raises(CannotInstall, match="SSE"):
        a.can_install(_make_entry(transport="sse"))


def test_codex_diff_renders_http_entry(monkeypatch, tmp_path):
    """#74: http entries land with `url` and `http_headers` keys in TOML."""
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexAdapter()
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    entry = _make_entry(
        name="remote-mcp",
        transport="http",
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer xyz"},
    )
    actions = a.diff("user", tmp_path, [entry])
    assert len(actions) == 1
    rendered = actions[0].contents.decode("utf-8")
    assert "[mcp_servers.remote-mcp]" in rendered
    assert 'url = "https://example.com/mcp"' in rendered
    assert "http_headers" in rendered
    assert 'Authorization = "Bearer xyz"' in rendered
    # http entries must NOT carry stdio keys
    assert "command =" not in rendered


def test_codex_diff_http_entry_without_url_raises(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter
    from agent_toolkit_cli.harness_adapters.base import CannotInstall

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexAdapter()
    (tmp_path / ".codex").mkdir()
    entry = _make_entry(name="bad", transport="http")  # no url
    with pytest.raises(CannotInstall, match="spec.mcp.url required"):
        a.diff("user", tmp_path, [entry])


def test_codex_diff_mixed_stdio_and_http_entries(monkeypatch, tmp_path):
    """Both transports can live in the same config side-by-side."""
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexAdapter()
    (tmp_path / ".codex").mkdir()
    stdio_entry = _make_entry(name="local-mcp", args=["-y", "pkg"])
    http_entry = _make_entry(
        name="remote-mcp", transport="http", url="https://x/y",
    )
    actions = a.diff("user", tmp_path, [stdio_entry, http_entry])
    assert len(actions) == 1
    rendered = actions[0].contents.decode("utf-8")
    assert "[mcp_servers.local-mcp]" in rendered
    assert "[mcp_servers.remote-mcp]" in rendered
    assert 'command = "npx"' in rendered
    assert 'url = "https://x/y"' in rendered


def test_codex_diff_creates_file_when_missing(monkeypatch, tmp_path):
    """No config.toml on disk → one create-action with rendered bytes."""
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexAdapter()
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    actions = a.diff("user", tmp_path, [entry])
    assert len(actions) == 1
    act = actions[0]
    assert act.path == target
    assert act.op == "create"
    assert act.bytes_before is None
    assert act.bytes_after is not None
    assert b"[mcp_servers.context7]" in act.contents
    assert b'command = "npx"' in act.contents
    assert b'args = ["-y", "@upstash/context7-mcp"]' in act.contents


def test_codex_diff_updates_existing_file_preserving_other_sections(monkeypatch, tmp_path):
    """Adding an MCP to a file with other sections yields one update-action;
    `[notice.*]` and top-level scalars are preserved."""
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    target.write_text(
        "# Pre-existing.\n"
        "model_provider = \"openai\"\n"
        "\n"
        "[notice.x]\n"
        "y = 1\n"
    )
    a = CodexAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    actions = a.diff("user", tmp_path, [entry])
    assert len(actions) == 1
    act = actions[0]
    assert act.op == "update"
    assert act.bytes_before == len(target.read_bytes())
    # Pre-existing tables/scalars preserved.
    assert b"[notice.x]" in act.contents
    assert b'model_provider = "openai"' in act.contents
    assert b"[mcp_servers.context7]" in act.contents


def test_codex_diff_unchanged_when_aligned(monkeypatch, tmp_path):
    """If on-disk already matches the desired render, diff returns []."""
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()

    a = CodexAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    # First call: create. Apply by writing the rendered contents.
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    # Second call: should be empty.
    actions2 = a.diff("user", tmp_path, [entry])
    assert actions2 == []


def test_codex_unlink_removes_managed_entry_via_previously_allowed(monkeypatch, tmp_path):
    """unlink semantics: entries=[], previously_allowed={'context7'} → removes context7."""
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()

    a = CodexAdapter()
    # Initial: link context7.
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [link_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(link_act.contents)
    assert b"[mcp_servers.context7]" in target.read_bytes()

    # Unlink: entries is empty, previously_allowed says context7 was ours.
    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    assert len(actions) == 1
    act = actions[0]
    assert act.op == "update"
    assert b"[mcp_servers.context7]" not in act.contents


def test_codex_unlink_does_not_touch_handrolled_entries(monkeypatch, tmp_path):
    """Names not in previously_allowed | current_entries are hand-rolled — preserved."""
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    target.write_text(
        "# Hand-rolled by user.\n"
        "[mcp_servers.preexisting]\n"
        "command = \"node\"\n"
        "args = [\"./local-mcp.js\"]\n"
    )

    a = CodexAdapter()
    # Link context7.
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [link_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(link_act.contents)
    after_link = target.read_bytes()
    assert b"[mcp_servers.context7]" in after_link
    assert b"[mcp_servers.preexisting]" in after_link  # AC#3: untouched

    # Unlink context7. preexisting is NOT in previously_allowed, so it's hand-rolled.
    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    assert len(actions) == 1
    act = actions[0]
    assert b"[mcp_servers.context7]" not in act.contents
    assert b"[mcp_servers.preexisting]" in act.contents


def test_codex_link_unlink_round_trip_byte_equal(monkeypatch, tmp_path):
    """AC #8: source with comments + unknown sections + hand-rolled MCP →
    link an unrelated MCP → unlink it → byte-equal to source.
    """
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    src = (
        b"# Codex config.\n"
        b"model_provider = \"openai\"\n"
        b"\n"
        b"[notice.model_migrations]\n"
        b"sonnet_4 = { migrated_at = \"2026-04-01\" }\n"
        b"\n"
        b"[tui.model_availability_nux]\n"
        b"shown = true\n"
        b"\n"
        b"[mcp_servers.preexisting]\n"
        b"command = \"node\"\n"
        b"args = [\"./local-mcp.js\"]\n"
    )
    target.write_bytes(src)

    a = CodexAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    # Link context7. previously_allowed is empty (it's brand new).
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    # Unlink context7. previously_allowed={"context7"}.
    actions = a.diff("user", tmp_path, [], previously_allowed={"context7"})
    assert len(actions) == 1
    target.write_bytes(actions[0].contents)

    after = target.read_bytes()
    assert after == src, (
        "Round-trip is NOT byte-equal — adapter design assumes it is.\n"
        f"Length src={len(src)} after={len(after)}.\n"
    )


def test_codex_list_installed_returns_all_mcp_servers_tables(monkeypatch, tmp_path):
    """list_installed enumerates every [mcp_servers.X] in the file (managed or not)."""
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    target.write_text(
        "[mcp_servers.context7]\n"
        "command = \"npx\"\n"
        "\n"
        "[mcp_servers.preexisting]\n"
        "command = \"node\"\n"
    )
    a = CodexAdapter()
    assert a.list_installed("user", tmp_path) == {"context7", "preexisting"}


def test_codex_list_installed_missing_file_returns_empty(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    a = CodexAdapter()
    assert a.list_installed("user", tmp_path) == set()


def test_codex_entry_drift_false_when_aligned(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    a = CodexAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    assert a.entry_drift("user", tmp_path, entry) is False


def test_codex_entry_drift_true_after_hand_edit(monkeypatch, tmp_path):
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    a = CodexAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    # User hand-edits the args array inside the managed entry.
    text = target.read_text().replace(
        '["-y", "@upstash/context7-mcp"]', '["-y", "@upstash/context7-mcp", "--debug"]'
    )
    target.write_text(text)

    assert a.entry_drift("user", tmp_path, entry) is True


def test_codex_re_link_byte_identical_when_already_linked(monkeypatch, tmp_path):
    """AC #2: re-running link with same allow-list yields no write."""
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    a = CodexAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    [first_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(first_act.contents)

    # previously_allowed is the YAML state from before the no-op re-link,
    # which is the same {context7}. Diff should be empty.
    actions = a.diff("user", tmp_path, [entry], previously_allowed={"context7"})
    assert actions == []
