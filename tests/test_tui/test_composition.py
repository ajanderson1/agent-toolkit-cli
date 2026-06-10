"""Column composition for the Standard / Non-standard matrix groups (#351)."""
from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_tui.composition import (
    BIG_FIVE,
    LONGTAIL_KEY,
    instructions_longtail,
    instructions_nonstandard_big_five,
    skills_longtail,
    skills_nonstandard_big_five,
)


def test_big_five_members():
    assert BIG_FIVE == ("claude-code", "pi", "codex", "gemini-cli", "opencode")


def test_skills_nonstandard_big_five_today():
    # codex / gemini-cli / opencode read .agents/skills → standard for skills.
    assert skills_nonstandard_big_five() == ("claude-code", "pi")


def test_skills_longtail_properties():
    tail = skills_longtail()
    assert tail == tuple(sorted(tail))                      # deterministic order
    assert set(tail).isdisjoint(BIG_FIVE)                   # big five never in tail
    assert set(tail).isdisjoint({"standard", "standard-skill", "standard-agent"})
    for name in tail:
        assert not AGENTS[name].is_standard                 # tail is non-compliant only
    assert len(tail) > 10                                   # sanity: tail is the long tail


def test_skills_sets_partition_catalog():
    standard = {n for n, c in AGENTS.items() if c.is_standard and c.show_in_standard_list}
    cols = set(skills_nonstandard_big_five()) | set(skills_longtail())
    assert cols.isdisjoint(standard)


def test_instructions_composition_today():
    assert instructions_nonstandard_big_five() == ("claude-code", "gemini-cli")
    tail = instructions_longtail()
    assert tail == tuple(sorted(tail))
    assert set(tail) == {"augment", "codebuddy", "iflow-cli", "replit", "tabnine-cli"}


def test_longtail_key_is_not_a_catalog_name():
    assert LONGTAIL_KEY not in AGENTS
