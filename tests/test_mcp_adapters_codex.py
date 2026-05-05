"""Codex adapter — ConfigFileAdapter against ~/.codex/config.toml."""
from __future__ import annotations

from pathlib import Path

import pytest


def _make_entry(name: str = "context7", *, transport: str = "stdio",
                command: str = "npx", args: list[str] | None = None,
                env: dict[str, str] | None = None):
    from agent_toolkit.harness_adapters.base import McpEntry

    inner: dict = {"command": command}
    if args is not None:
        inner["args"] = args
    if env is not None:
        inner["env"] = env
    return McpEntry(
        name=name,
        inner_config=inner,
        mcp_spec={"transport": transport, "install_method": "npx"},
    )


def test_codex_adapter_basic_attrs():
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    a = CodexAdapter()
    assert a.name == "codex"
    assert a.strategy == "config_file"


def test_codex_user_config_target(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexAdapter()
    assert a.config_target("user", tmp_path) == tmp_path / ".codex" / "config.toml"


def test_codex_project_config_target_requires_dir(tmp_path):
    """Project target only set when .codex/ exists in project_root."""
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    proj = tmp_path / "p"
    proj.mkdir()
    a = CodexAdapter()
    # No .codex/ → no target
    assert a.config_target("project", proj) is None
    # Create .codex/ → target appears
    (proj / ".codex").mkdir()
    assert a.config_target("project", proj) == proj / ".codex" / "config.toml"


def test_codex_can_install_accepts_stdio():
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    a = CodexAdapter()
    a.can_install(_make_entry(transport="stdio"))  # no exception


def test_codex_can_install_refuses_http():
    from agent_toolkit.harness_adapters.codex import CodexAdapter
    from agent_toolkit.harness_adapters.base import CannotInstall

    a = CodexAdapter()
    with pytest.raises(CannotInstall, match="stdio"):
        a.can_install(_make_entry(transport="http"))


def test_codex_diff_creates_file_when_missing(monkeypatch, tmp_path):
    """No config.toml on disk → one create-action with rendered bytes."""
    from agent_toolkit.harness_adapters.codex import CodexAdapter

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


def test_codex_diff_updates_existing_file(monkeypatch, tmp_path):
    """Adding a new MCP to a file with existing content yields one update-action."""
    from agent_toolkit.harness_adapters.codex import CodexAdapter

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
    # Pre-existing tables preserved.
    assert b"[notice.x]" in act.contents
    assert b'model_provider = "openai"' in act.contents
    assert b"[mcp_servers.context7]" in act.contents


def test_codex_diff_unchanged_when_aligned(monkeypatch, tmp_path):
    """If on-disk already matches the desired render, diff returns []."""
    from agent_toolkit.harness_adapters.codex import CodexAdapter

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


def test_codex_unlink_removes_one_entry_preserving_siblings(monkeypatch, tmp_path):
    """unlink() = re-render with entry absent. Siblings remain byte-equal."""
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    target.write_text(
        "# Hand-rolled by user.\n"
        "model_provider = \"openai\"\n"
        "\n"
        "[mcp_servers.preexisting]\n"
        "command = \"node\"\n"
        "args = [\"./local-mcp.js\"]\n"
    )

    a = CodexAdapter()
    # Allow-list contains only context7 (newly link it).
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [link_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(link_act.contents)
    after_link = target.read_bytes()
    assert b"[mcp_servers.context7]" in after_link
    assert b"[mcp_servers.preexisting]" in after_link  # AC #3: untouched

    # Now allow-list is empty (unlink). Diff with [] should produce one
    # update removing context7 only, preserving preexisting.
    actions = a.diff("user", tmp_path, [])
    assert len(actions) == 1
    act = actions[0]
    assert b"[mcp_servers.context7]" not in act.contents
    assert b"[mcp_servers.preexisting]" in act.contents


def test_codex_link_unlink_round_trip_byte_equal(monkeypatch, tmp_path):
    """AC #8: source with comments + unknown sections + hand-rolled MCP →
    link an unrelated MCP → unlink it → byte-equal to source.
    """
    from agent_toolkit.harness_adapters.codex import CodexAdapter

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

    # Link
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    # Unlink (allow-list now contains only the preexisting hand-rolled, which
    # this adapter doesn't manage — pass [] for managed entries).
    actions = a.diff("user", tmp_path, [])
    assert len(actions) == 1
    target.write_bytes(actions[0].contents)

    after = target.read_bytes()
    assert after == src, (
        "Round-trip is NOT byte-equal — adapter design assumes it is.\n"
        f"Length src={len(src)} after={len(after)}.\n"
    )


def test_codex_list_installed_returns_managed_entry_names(monkeypatch, tmp_path):
    """list_installed enumerates [mcp_servers.X] tables present in the file."""
    from agent_toolkit.harness_adapters.codex import CodexAdapter

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
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    a = CodexAdapter()
    assert a.list_installed("user", tmp_path) == set()


def test_codex_entry_drift_false_when_aligned(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    a = CodexAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    assert a.entry_drift("user", tmp_path, entry) is False


def test_codex_entry_drift_true_after_hand_edit(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.codex import CodexAdapter

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
