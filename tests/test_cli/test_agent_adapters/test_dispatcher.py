"""agent_adapters.get_adapter() dispatches to per-mechanism modules."""
from __future__ import annotations

from typing import get_args, get_type_hints

import pytest


def test_get_adapter_raises_for_unknown_harness():
    from agent_toolkit_cli.agent_adapters import get_adapter
    from agent_toolkit_cli.skill_agents import UnknownAgentError
    with pytest.raises(UnknownAgentError):
        get_adapter("nonexistent-harness-xyz")


def test_get_adapter_raises_for_none_mechanism_harness():
    """A harness with subagent_mechanism='none' has no installable adapter.

    Asserts the precondition on `amp` so this test fails loudly if Task 11
    (or a future PR) re-classifies amp to a real mechanism — without the
    precondition check, the assertion below would become vacuously-passing.
    """
    from agent_toolkit_cli.agent_adapters import (
        UnsupportedMechanismError, get_adapter,
    )
    from agent_toolkit_cli.skill_agents import AGENTS
    assert AGENTS["amp"].subagent_mechanism == "none", (
        "amp must remain mechanism='none' for this test to be meaningful — "
        "pick another by-design cell if amp gets re-classified."
    )
    with pytest.raises(UnsupportedMechanismError):
        get_adapter("amp")


def test_agent_adapter_protocol_callable():
    """AgentAdapter Protocol exposes install + uninstall."""
    from agent_toolkit_cli.agent_adapters import AgentAdapter
    assert hasattr(AgentAdapter, "install")
    assert hasattr(AgentAdapter, "uninstall")


def test_dispatcher_handles_every_subagent_mechanism_literal():
    """The dispatcher must have a branch for every value of the
    subagent_mechanism Literal. If a 5th value is ever added to the
    annotation without updating get_adapter, this test catches it
    BEFORE production code routes to the 'unreachable' RuntimeError."""
    from agent_toolkit_cli.skill_agents import AgentConfig

    # Lazy import to keep agent_adapters/__init__ importable in isolation.
    import agent_toolkit_cli.agent_adapters as agent_adapters  # noqa: F401

    hints = get_type_hints(AgentConfig)
    literal_values = set(get_args(hints["subagent_mechanism"]))
    # Every non-"none" literal must have a branch in get_adapter. We can't
    # introspect the if/elif chain directly, but we can assert each value
    # routes WITHOUT raising "unreachable" — by monkeypatching a fake harness.
    # Cheap proxy: enumerate values and confirm they're each handled in source.
    import inspect
    src = inspect.getsource(agent_adapters.get_adapter)
    for value in literal_values:
        if value == "none":
            continue  # handled by the early UnsupportedMechanismError branch
        assert f'mech == "{value}"' in src, (
            f"agent_adapters.get_adapter has no branch for subagent_mechanism "
            f"value '{value}'. Add the dispatch + import the mechanism module."
        )


@pytest.mark.xfail(
    strict=False,
    reason="subagent_mechanism literals are set in Task 11; "
           "test body runs but get_adapter('claude-code') currently routes "
           "to UnsupportedMechanismError because mechanism is still 'none'.",
)
def test_get_adapter_returns_callable():
    """For a harness with a real mechanism, returns an object with install/uninstall."""
    from agent_toolkit_cli.agent_adapters import get_adapter
    adapter = get_adapter("claude-code")
    assert callable(getattr(adapter, "install", None))
    assert callable(getattr(adapter, "uninstall", None))
