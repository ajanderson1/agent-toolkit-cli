"""get_adapter is kind-aware: codex+mcp → CodexAdapter, codex+hook → CodexHookAdapter."""
from __future__ import annotations


def test_get_adapter_codex_mcp_returns_mcp_adapter():
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    a = get_adapter("codex", "mcp")
    assert isinstance(a, CodexAdapter)
    assert a.strategy == "config_file"


def test_get_adapter_codex_hook_returns_hook_adapter():
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.codex_hook import CodexHookAdapter

    a = get_adapter("codex", "hook")
    assert isinstance(a, CodexHookAdapter)
    assert a.strategy == "config_file+folder"


def test_get_adapter_default_kind_is_mcp_for_backcompat():
    """Existing callers that don't pass kind must keep working."""
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.codex import CodexAdapter

    a = get_adapter("codex")
    assert isinstance(a, CodexAdapter)


def test_get_adapter_unknown_harness_raises():
    import pytest
    from agent_toolkit_cli.harness_adapters import get_adapter

    with pytest.raises(ValueError, match="unknown harness"):
        get_adapter("nope", "mcp")
