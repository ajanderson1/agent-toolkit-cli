"""Adapter registry + base types tests."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_get_adapter_returns_codex_adapter():
    from agent_toolkit_cli.harness_adapters import get_adapter

    a = get_adapter("codex")
    assert a.name == "codex"
    assert a.strategy == "config_file"


def test_get_adapter_unknown_harness_raises():
    from agent_toolkit_cli.harness_adapters import get_adapter

    with pytest.raises(ValueError, match="unknown harness"):
        get_adapter("nonexistent")


def test_get_adapter_returns_unimplemented_for_pending_harnesses():
    """Pi remains UnimplementedAdapter (Pi has no MCP support by design)."""
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter

    for h in ("pi",):
        a = get_adapter(h)
        assert isinstance(a, UnimplementedAdapter), f"{h} should be UnimplementedAdapter"
        assert a.name == h


def test_unimplemented_adapter_skip_message():
    """UnimplementedAdapter exposes a stable message for the loud-skip path."""
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter

    a = UnimplementedAdapter("claude")
    msg = a.skip_message()
    assert "claude" in msg
    # Defaults to MCP for back-compat with existing callers; the "MCP"
    # capitalisation is preserved so existing log-greps still match.
    assert "MCP adapter" in msg


def test_unimplemented_adapter_skip_message_kind_aware():
    """#123: when the sentinel is constructed for a non-mcp kind, the skip
    message names that kind rather than mis-labelling it as an MCP adapter.
    """
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter

    a = UnimplementedAdapter("claude", kind="hook")
    assert "hook adapter" in a.skip_message()
    assert "MCP" not in a.skip_message()


def test_get_adapter_unimplemented_propagates_kind():
    """get_adapter('<harness>', kind='hook') for a pair with no adapter must
    return an UnimplementedAdapter whose skip message names the hook kind.
    """
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter

    a = get_adapter("claude", kind="hook")
    assert isinstance(a, UnimplementedAdapter)
    assert a.kind == "hook"
    assert "hook adapter" in a.skip_message()


def test_mcp_entry_dataclass_is_frozen():
    """McpEntry is frozen so its fields can't be reassigned after construction."""
    from agent_toolkit_cli.harness_adapters.base import McpEntry

    e1 = McpEntry(name="x", inner_config={"a": 1}, mcp_spec={"transport": "stdio"})
    with pytest.raises((AttributeError, Exception)):
        e1.name = "y"  # frozen


def test_write_action_carries_contents_for_writes():
    """WriteAction for create/update carries `contents` bytes; delete has None."""
    from agent_toolkit_cli.harness_adapters.base import WriteAction

    a = WriteAction(
        path=Path("/tmp/x"), op="create", bytes_before=None, bytes_after=10,
        contents=b"hello world",
    )
    assert a.contents == b"hello world"

    d = WriteAction(
        path=Path("/tmp/x"), op="delete", bytes_before=10, bytes_after=None,
        contents=None,
    )
    assert d.contents is None


def test_cannot_install_is_exception():
    """CannotInstall is a regular exception."""
    from agent_toolkit_cli.harness_adapters.base import CannotInstall

    with pytest.raises(CannotInstall, match="bad-mcp"):
        raise CannotInstall("bad-mcp: transport http unsupported")


def test_get_adapter_returns_real_claude_adapter():
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter

    a = get_adapter("claude")
    assert not isinstance(a, UnimplementedAdapter)
    assert a.name == "claude"
    assert a.strategy == "config_file"


def test_get_adapter_returns_real_opencode_adapter():
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter

    a = get_adapter("opencode")
    assert not isinstance(a, UnimplementedAdapter)
    assert a.name == "opencode"
    assert a.strategy == "config_file"


def test_get_adapter_pi_remains_unimplemented():
    """Pi MCP is unsupported by design; adapter stays UnimplementedAdapter."""
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter

    a = get_adapter("pi")
    assert isinstance(a, UnimplementedAdapter)
