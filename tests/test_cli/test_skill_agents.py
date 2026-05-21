"""Tests for the agents catalog (skill_agents.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.skill_agents import (
    AGENTS,
    UnknownAgentError,
    get_agent,
    get_non_universal_agents,
    get_universal_agents,
    is_universal,
)


def test_catalog_has_55_entries():
    """54 real agents + 1 synthetic 'universal' pseudo-entry."""
    assert len(AGENTS) == 55


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
