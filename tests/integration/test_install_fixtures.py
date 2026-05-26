"""Integration: install-shaped fixtures land a real canonical + lock entry."""
from agent_toolkit_cli.skill_git import is_git_repo


def test_installed_skill_has_git_canonical(installed_skill):
    assert is_git_repo(installed_skill.canonical)
    assert installed_skill.slug in installed_skill.lock_text


def test_copymode_skill_has_no_git(copymode_skill):
    assert not is_git_repo(copymode_skill.canonical)


def test_monorepo_skill_is_read_only(monorepo_skill):
    assert monorepo_skill.read_only is True
