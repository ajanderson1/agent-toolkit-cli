"""Deprecated token aliases (#350): old spellings warn + map for one cycle."""
import pytest

from agent_toolkit_cli.skill_agents import (
    AGENTS,
    DEPRECATED_TOKEN_ALIASES,
    _warned_deprecated,
    resolve_agent_token,
)


@pytest.fixture(autouse=True)
def _reset_warned():
    _warned_deprecated.clear()
    yield
    _warned_deprecated.clear()


@pytest.mark.parametrize("old,new", sorted(DEPRECATED_TOKEN_ALIASES.items()))
def test_alias_maps_old_to_new(old, new):
    assert resolve_agent_token(old) == new


def test_expected_alias_table():
    # Only tokens a user could actually have typed at a CLI boundary.
    # general-instructions / general-pi-extension were never accepted values
    # anywhere, so aliasing them would warn-then-error on a token the user
    # never typed (review finding — deliberately excluded).
    assert DEPRECATED_TOKEN_ALIASES == {
        "universal": "standard",
        "general-skill": "standard-skill",
        "general-agent": "standard-agent",
    }


def test_new_and_unknown_tokens_pass_through():
    assert resolve_agent_token("standard") == "standard"
    assert resolve_agent_token("claude-code") == "claude-code"
    assert resolve_agent_token("nope") == "nope"  # validation stays at callers


def test_warning_printed_once_per_token(capsys):
    resolve_agent_token("universal")
    resolve_agent_token("universal")
    err = capsys.readouterr().err
    assert err.count("deprecated") == 1
    assert "'standard'" in err and "v4" in err


def test_aliased_catalog_targets_exist():
    for new in DEPRECATED_TOKEN_ALIASES.values():
        assert new in AGENTS


from agent_toolkit_cli.commands.skill import _resolve_agents


def test_resolve_agents_accepts_deprecated_universal(capsys):
    assert _resolve_agents("universal", "global") == ("standard",)
    assert "deprecated" in capsys.readouterr().err


def test_resolve_agents_accepts_new_token_silently(capsys):
    assert _resolve_agents("standard", "global") == ("standard",)
    assert capsys.readouterr().err == ""


def test_resolve_agents_still_rejects_unknown():
    import click
    with pytest.raises(click.UsageError):
        _resolve_agents("definitely-not-a-harness", "global")


def test_resolve_agents_old_synthetic_spelling_still_rejected():
    import click
    with pytest.raises(click.UsageError, match="synthetic"):
        _resolve_agents("general-skill", "global")  # aliases to standard-skill, then rejected
