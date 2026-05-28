"""Tests for the agents catalog (skill_agents.py)."""
from __future__ import annotations

import pytest

from agent_toolkit_cli.skill_agents import (
    AGENTS,
    UnknownAgentError,
    get_agent,
    get_non_universal_agents,
    get_universal_agents,
    is_universal,
)


def test_catalog_size():
    """54 real agents + 1 synthetic 'universal' pseudo-entry."""
    # +1 for general-skill (PR1 of v3.0.0, coexists with universal)
    # +1 for general-agent (PR2 of v3.0.0)
    assert len(AGENTS) == 57


def test_every_entry_key_matches_its_name():
    for key, cfg in AGENTS.items():
        assert cfg.name == key, f"{key!r} name mismatch: {cfg.name!r}"


def test_every_global_skills_dir_is_absolute():
    for key, cfg in AGENTS.items():
        assert cfg.global_skills_dir.is_absolute(), (
            f"{key} global_skills_dir not absolute: {cfg.global_skills_dir}"
        )


def test_universal_agents_have_canonical_skills_dir():
    for n in get_universal_agents():
        assert AGENTS[n].skills_dir == ".agents/skills"


def test_non_universal_agents_have_custom_skills_dir():
    for n in get_non_universal_agents():
        assert AGENTS[n].skills_dir != ".agents/skills"


def test_universal_list_excludes_synthetic_universal():
    assert "universal" not in get_universal_agents()


def test_universal_list_excludes_replit():
    """replit has skills_dir='.agents/skills' but show_in_universal_list=False."""
    assert "replit" not in get_universal_agents()


def test_is_universal_matches_skills_dir():
    assert is_universal("codex") is True
    assert is_universal("claude-code") is False
    assert is_universal("pi") is False


def test_get_agent_returns_config():
    cfg = get_agent("claude-code")
    assert cfg.display_name == "Claude Code"
    assert cfg.skills_dir == ".claude/skills"


def test_get_agent_raises_unknown():
    with pytest.raises(UnknownAgentError):
        get_agent("not-a-real-agent")


def test_well_known_agents_present():
    """Our 5 v2.0.0 shortlist all exist in the catalog under skills.sh names."""
    for name in ("claude-code", "codex", "opencode", "gemini-cli", "pi"):
        assert name in AGENTS, f"{name} missing from catalog"


def test_well_known_universality():
    """Of our 5 v2.0.0 shortlist:
    codex, opencode, gemini-cli are universal; claude-code, pi are not."""
    assert is_universal("codex") is True
    assert is_universal("opencode") is True
    assert is_universal("gemini-cli") is True
    assert is_universal("claude-code") is False
    assert is_universal("pi") is False


def test_general_skill_entry_exists_and_resolves_to_dotagents_skills():
    assert "general-skill" in AGENTS
    cfg = AGENTS["general-skill"]
    assert cfg.skills_dir == ".agents/skills"
    assert cfg.show_in_universal_list is False
    assert cfg.is_universal is True  # by skills_dir membership


def test_universal_and_general_skill_coexist_with_same_dir():
    """PR1 ships both. The `universal` synthetic is removed in PR3."""
    assert AGENTS["universal"].skills_dir == AGENTS["general-skill"].skills_dir
    assert AGENTS["universal"].global_skills_dir == AGENTS["general-skill"].global_skills_dir


def test_get_universal_agents_does_not_include_general_skill():
    """Both `universal` and `general-skill` set show_in_universal_list=False,
    so neither appears in the legacy 'universal agents' listing."""
    listed = get_universal_agents()
    assert "universal" not in listed
    assert "general-skill" not in listed


def test_list_cmd_rejects_general_skill_token():
    """general-skill is in AGENTS but the CLI must reject it as a token."""
    import click as _click  # noqa: F401 — for type clarity
    from click.testing import CliRunner

    from agent_toolkit_cli.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "list", "-g", "-a", "general-skill"])
    assert result.exit_code != 0
    assert "general-skill is a synthetic" in result.output


def test_resolve_agents_rejects_general_skill_token():
    """_resolve_agents() must fail-loud on general-skill."""
    import click

    from agent_toolkit_cli.commands.skill import _resolve_agents

    with pytest.raises(click.UsageError, match="general-skill is a synthetic"):
        _resolve_agents("general-skill", "global")
    with pytest.raises(click.UsageError, match="general-skill is a synthetic"):
        _resolve_agents("claude-code,general-skill", "global")


def test_agentconfig_has_subagent_mechanism_field():
    from agent_toolkit_cli.skill_agents import AGENTS, AgentConfig

    cfg = AGENTS["claude-code"]
    assert hasattr(cfg, "subagent_mechanism")


def test_subagent_mechanism_default_is_none():
    """Unset cells default to 'none' so existing callers continue working.
    'amp' is not in the 28 supported list per the matrix, so its mechanism
    stays 'none' even after Task 11 wires the supported cells."""
    from agent_toolkit_cli.skill_agents import AGENTS

    assert AGENTS["amp"].subagent_mechanism == "none"


def test_subagent_mechanism_literal_values():
    """The field's Literal annotation pins exactly the four documented values.

    A typo in a future cell ('symlinks' or 'translater') will route silently
    to the 'none' branch in the adapter dispatcher; pinning the value set
    here is the cheapest place to fail loud.
    """
    from typing import get_args, get_type_hints

    from agent_toolkit_cli.skill_agents import AgentConfig

    hints = get_type_hints(AgentConfig)
    assert "subagent_mechanism" in hints
    assert set(get_args(hints["subagent_mechanism"])) == {
        "symlink", "translate", "config_file_folder", "none",
    }


def test_general_agent_synthetic_present():
    from agent_toolkit_cli.skill_agents import AGENTS, XDG_CONFIG

    assert "general-agent" in AGENTS
    cfg = AGENTS["general-agent"]
    assert cfg.skills_dir == ".agents/agents"  # parallel to general-skill but agents dir
    assert cfg.global_skills_dir == XDG_CONFIG / "agents/agents"
    assert cfg.show_in_universal_list is False
    assert cfg.subagent_mechanism == "none"  # not a real harness
