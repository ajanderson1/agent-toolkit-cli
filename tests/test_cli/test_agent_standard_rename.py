"""#350 — full universal/general → standard rename: pins the renamed tokens.

Originally written for the #304 display-only rename (PR3); now pins the #350
full rename, where catalog keys, synthetic-name sets, and display names all
say "standard".

Asserts:
1. The agent facade's synthetic name set contains "standard-agent" (catalog
   already has the entry; this pins the facade constant).
2. The skill facade's synthetic name set contains "standard-skill" (catalog
   already has the entry; this pins the skill facade constant).
3. Dual-flagged agent cells (is_standard=True + a real subagent_mechanism,
   e.g. cursor with mechanism='symlink') are NOT silently skipped by
   _install_core._should_skip_symlink when queried at global scope.
   Before the PR3 fix, _should_skip_symlink returned (True, 'universal-global')
   for any is_standard cell regardless of mechanism — this is wrong for cells
   that also have a real agent adapter.
4. agent_install.plan() for cursor at global scope includes cursor in
   add_agents (end-to-end assertion of the same fix, via the agent facade's
   adapter-aware scanner which already bypasses _should_skip_symlink).
"""
from __future__ import annotations

import pytest


# ── 1. Synthetic name constants ─────────────────────────────────────────────


def test_agent_synthetic_name_is_general_agent():
    """The agent facade's synthetic set uses 'standard-agent', not 'standard'."""
    from agent_toolkit_cli.agent_install import _AGENT_SYNTHETIC_NAMES
    assert "standard-agent" in _AGENT_SYNTHETIC_NAMES
    assert "standard" not in _AGENT_SYNTHETIC_NAMES


def test_skill_synthetic_names_include_general_skill():
    """The skill facade's synthetic set contains 'standard-skill'."""
    from agent_toolkit_cli.skill_install import _SKILL_SYNTHETIC_NAMES
    assert "standard-skill" in _SKILL_SYNTHETIC_NAMES


def test_general_agent_catalog_entry_exists():
    """Catalog already ships 'standard-agent' (PR2). This test pins the shape."""
    from agent_toolkit_cli.skill_agents import AGENTS
    assert "standard-agent" in AGENTS
    cfg = AGENTS["standard-agent"]
    assert cfg.display_name == "Standard (agents)"
    assert cfg.show_in_standard_list is False
    assert cfg.subagent_mechanism == "none"  # synthetic — not a real harness


def test_general_skill_catalog_entry_exists():
    """Catalog already ships 'standard-skill' (PR1). This test pins the shape."""
    from agent_toolkit_cli.skill_agents import AGENTS
    assert "standard-skill" in AGENTS
    cfg = AGENTS["standard-skill"]
    assert cfg.display_name == "Standard (skills)"
    assert cfg.show_in_standard_list is False
    assert cfg.is_standard is True  # lives in .agents/skills


# ── 2. Dual-flagged cell skip predicate ─────────────────────────────────────


@pytest.mark.parametrize("harness", [
    "cursor",       # is_standard=True, subagent_mechanism='symlink'
    "gemini-cli",   # is_standard=True, subagent_mechanism='translate'
    "github-copilot",  # is_standard=True, subagent_mechanism='translate'
    "opencode",     # is_standard=True, subagent_mechanism='translate'
])
def test_skip_predicate_does_not_skip_dual_flagged_agent_cells(harness):
    """_should_skip_symlink must NOT skip dual-flagged cells at global scope.

    A dual-flagged cell has is_standard=True (skills_dir='.agents/skills')
    AND a real subagent_mechanism (not 'none').  Before the PR3 fix, the
    predicate treated is_standard as a generic skip signal: it returned
    (True, 'universal-global') for any universal cell regardless of whether
    it had a real agent adapter.  This silently omitted dual-flagged cells
    from the core's _current_linked_agents scan even though they are
    legitimate agent install targets.

    After the fix the predicate is asset-type-aware: it only skips cells that are
    universal AND have no real agent mechanism (subagent_mechanism='none').
    """
    from agent_toolkit_cli.skill_agents import AGENTS
    from agent_toolkit_cli._install_core import _should_skip_symlink

    cfg = AGENTS[harness]
    # Pre-condition: the harness must be dual-flagged for the test to be meaningful.
    assert cfg.is_standard, f"{harness} must have is_standard=True"
    assert cfg.subagent_mechanism != "none", (
        f"{harness} must have a real subagent_mechanism for this test"
    )

    skip, reason = _should_skip_symlink(
        agent_name=harness, scope="global", project=None,
    )
    assert skip is False, (
        f"_should_skip_symlink incorrectly skips {harness!r} at global scope "
        f"(reason={reason!r}). Dual-flagged cells with a real agent mechanism "
        f"must NOT be skipped — their agent adapter handles the install."
    )
    assert reason == ""


def test_skip_predicate_still_skips_pure_universal_cell_at_global():
    """Pure universal cells (no real agent mechanism) must still be skipped.

    codex: is_standard=True, subagent_mechanism='none' (disabled PR2).
    Ensures the PR3 fix does not regress the skill asset type's universal-skip
    behaviour for cells that genuinely have no agent adapter.
    """
    from agent_toolkit_cli.skill_agents import AGENTS
    from agent_toolkit_cli._install_core import _should_skip_symlink

    cfg = AGENTS["codex"]
    assert cfg.is_standard is True
    assert cfg.subagent_mechanism == "none"

    skip, reason = _should_skip_symlink(
        agent_name="codex", scope="global", project=None,
    )
    assert skip is True
    assert reason == "standard-global"


def test_skip_predicate_does_not_skip_pure_universal_at_project():
    """Standard cells at project scope must never be skipped (existing rule)."""
    from agent_toolkit_cli._install_core import _should_skip_symlink
    skip, reason = _should_skip_symlink(
        agent_name="codex", scope="project", project=None,
    )
    assert skip is False
    assert reason == ""


# ── 3. agent_install.plan() includes dual-flagged cells ─────────────────────


def test_agent_plan_includes_cursor_at_global_scope(tmp_path, monkeypatch):
    """agent_install.plan() must include cursor in add_agents at global scope.

    cursor is dual-flagged: is_standard=True (reads .agents/skills for skills)
    + subagent_mechanism='symlink' (has a real agent adapter).  The agent
    facade's adapter-aware scanner bypasses _should_skip_symlink, so cursor
    should appear in add_agents regardless.

    This is the end-to-end guard: even if _should_skip_symlink were called
    somewhere in the agent path, the plan must still include the harness.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import plan

    p = plan(slug="test-agent", scope="global", target_agents=("cursor",))
    assert "cursor" in p.add_agents, (
        "cursor must appear in add_agents — dual-flagged cells must not be "
        "excluded from the agent install plan at global scope"
    )


def test_agent_plan_includes_gemini_cli_at_global_scope(tmp_path, monkeypatch):
    """gemini-cli is dual-flagged (is_standard + translate). Must be included."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.agent_install import plan

    p = plan(slug="test-agent", scope="global", target_agents=("gemini-cli",))
    assert "gemini-cli" in p.add_agents
