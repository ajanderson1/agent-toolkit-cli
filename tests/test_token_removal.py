"""#356: deprecated token aliases are removed — old spellings now raise.

Pins the hard break shipped as v4.0.0. Before #356 these spellings warned on
stderr and mapped to their 'standard' equivalents; after removal they are
unknown tokens and hit each caller's existing unknown-token guard.
"""
import click
import pytest

from agent_toolkit_cli.commands.skill import _resolve_agents
from agent_toolkit_cli.commands.agent._common import parse_harness_tokens


def test_resolver_symbols_are_gone():
    """The unambiguous RED anchor: these symbols exist pre-removal, gone after."""
    import agent_toolkit_cli.skill_agents as sa
    assert not hasattr(sa, "resolve_agent_token")
    assert not hasattr(sa, "DEPRECATED_TOKEN_ALIASES")
    assert not hasattr(sa, "_warned_deprecated")


# NOTE on RED honesty (verified live 2026-06-12): not every old spelling flips
# from pass→raise. `universal` and `general-agent` currently *map* (no raise) via
# _resolve_agents, so those are genuine REDs. `general-skill` already raises today
# because it maps to the synthetic `standard-skill` and hits the synthetic guard —
# it raises both before AND after (the *reason* changes, not the outcome). The
# asserts below are still correct post-removal; the genuine behaviour-flip is
# proven by `universal`/`general-agent` + the symbols test.
@pytest.mark.parametrize("token", ["universal", "general-skill", "general-agent"])
def test_skill_agents_old_spellings_now_raise(token):
    with pytest.raises(click.UsageError):
        _resolve_agents(token, "global")


@pytest.mark.parametrize("token", ["universal", "general-agent"])
def test_harness_old_spellings_now_raise(token):
    with pytest.raises(click.UsageError):
        parse_harness_tokens(token)


def test_old_spelling_emits_no_deprecation_warning(capsys):
    """Post-removal there is no warn-then-raise; just a clean unknown-token error."""
    with pytest.raises(click.UsageError):
        _resolve_agents("universal", "global")
    assert "deprecated" not in capsys.readouterr().err


def test_new_tokens_still_work_silently(capsys):
    assert _resolve_agents("standard", "global") == ("standard",)
    assert capsys.readouterr().err == ""


def test_unknown_token_still_raises():
    with pytest.raises(click.UsageError):
        _resolve_agents("definitely-not-a-harness", "global")
