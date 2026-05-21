"""Tests for the skill wizard prompts (uses _io_for_test hook)."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.commands.skill import skill as skill_group
from agent_toolkit_cli.commands.skill.wizard import (
    AgentSelection, RemoveMode, SlugSelection,
    select_agents_to_add, select_remove_mode, select_slug_to_remove,
)


def test_select_agents_to_add_returns_test_hook():
    result = select_agents_to_add(
        slug="x", canonical_path=Path("/tmp/x"),
        _io_for_test=AgentSelection(
            agents=("claude-code", "codex"), scope="global",
        ),
    )
    assert result.agents == ("claude-code", "codex")
    assert result.scope == "global"


def test_select_slug_to_remove_test_hook():
    result = select_slug_to_remove(
        installed_slugs=("a", "b"),
        slug_descriptions={"a": "linked: claude-code", "b": "linked: none"},
        _io_for_test=SlugSelection(slugs=("a",)),
    )
    assert result.slugs == ("a",)


def test_select_remove_mode_test_hook():
    result = select_remove_mode(
        slug="x", will_delete=("/tmp/x",),
        _io_for_test=RemoveMode(mode="full", confirmed=True),
    )
    assert result.mode == "full"


def test_skill_add_never_invokes_wizard(git_sandbox, tmp_path, monkeypatch):
    """v2.2: skill add is non-interactive; wizard is never called."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    from agent_toolkit_cli.commands.skill import wizard

    def boom(*a, **kw):
        raise AssertionError("wizard must not be called from skill add")

    monkeypatch.setattr(wizard, "select_agents_to_add", boom)

    runner = CliRunner()
    result = runner.invoke(
        skill_group,
        ["add", str(git_sandbox.upstream), "--slug", "demo"],
        env={**git_sandbox.env, "AGENT_TOOLKIT_SKILLS_ROOT": str(library_root)},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
