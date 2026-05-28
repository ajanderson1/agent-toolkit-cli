"""agent_adapters.get_adapter() dispatches to per-mechanism modules."""
from __future__ import annotations

import pytest


def test_get_adapter_raises_for_unknown_harness():
    from agent_toolkit_cli.agent_adapters import get_adapter
    from agent_toolkit_cli.skill_agents import UnknownAgentError
    with pytest.raises(UnknownAgentError):
        get_adapter("nonexistent-harness-xyz")


def test_get_adapter_raises_for_none_mechanism_harness():
    """A harness with subagent_mechanism='none' has no installable adapter."""
    from agent_toolkit_cli.agent_adapters import (
        UnsupportedMechanismError, get_adapter,
    )
    with pytest.raises(UnsupportedMechanismError):
        get_adapter("amp")  # known harness, but mechanism="none"


def test_agent_adapter_protocol_callable():
    """AgentAdapter Protocol exposes install + uninstall."""
    from agent_toolkit_cli.agent_adapters import AgentAdapter
    assert hasattr(AgentAdapter, "install")
    assert hasattr(AgentAdapter, "uninstall")


def test_get_adapter_returns_callable():
    """For a harness with a real mechanism, returns an object with install/uninstall.

    xfails until Task 11 sets the mechanism literals on real cells.
    """
    pytest.xfail("subagent_mechanism literals are set in Task 11")
    from agent_toolkit_cli.agent_adapters import get_adapter
    adapter = get_adapter("claude-code")
    assert callable(getattr(adapter, "install", None))
    assert callable(getattr(adapter, "uninstall", None))
