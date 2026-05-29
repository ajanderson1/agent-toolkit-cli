"""Tests for the legacy install()/uninstall() wrappers.

These use project scope throughout. Global scope now delegates to
agent_projection_dir(), which resolves to the real ~/.claude etc. at import
time — writing there from tests would pollute the developer's machine.
"""
from pathlib import Path

import pytest

from agent_toolkit_cli import skill_install
from agent_toolkit_cli._install_core import InstallPlan
from agent_toolkit_cli.skill_install import InstallError, install, uninstall
from agent_toolkit_cli.skill_paths import canonical_skill_dir
from agent_toolkit_cli.skill_source import ParsedSource, parse_source


def test_install_creates_canonical_and_symlinks(git_sandbox, tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    # Create agent root dirs so skip-rule 2 doesn't apply.
    (project / ".claude").mkdir()
    (project / ".codex").mkdir()
    src = parse_source(str(git_sandbox.upstream))
    install(
        parsed=src, slug="demo", scope="project",
        home=None, project=project, harnesses=("claude", "codex"),
        env=git_sandbox.env,
    )
    canonical = project / ".agents" / "skills" / "demo"
    assert (canonical / "SKILL.md").exists()
    claude = project / ".claude" / "skills" / "demo"
    # codex is universal → project scope creates a symlink at
    # <project>/.agents/skills/demo (same as canonical). No separate .codex link.
    assert claude.is_symlink() and Path(claude.resolve()) == canonical.resolve()


def test_install_is_idempotent(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    src = parse_source(str(git_sandbox.upstream))
    install(parsed=src, slug="demo", scope="project", home=None, project=project,
            harnesses=("claude",), env=git_sandbox.env)
    install(parsed=src, slug="demo", scope="project", home=None, project=project,
            harnesses=("claude",), env=git_sandbox.env)
    canonical = canonical_skill_dir("demo", scope="project", project=project)
    assert (canonical / "SKILL.md").exists()


def test_install_refuses_to_overwrite_unrelated_symlink(git_sandbox, tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    claude_skills = project / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    (claude_skills / "demo").symlink_to(foreign)
    src = parse_source(str(git_sandbox.upstream))
    with pytest.raises(InstallError, match="conflicting symlink") as excinfo:
        install(
            parsed=src, slug="demo", scope="project",
            home=None, project=project, harnesses=("claude",),
            env=git_sandbox.env,
        )
    # The error points the user at doctor, the escape hatch for stray links.
    msg = str(excinfo.value)
    assert "skill doctor -p" in msg
    assert "stray symlinks" in msg


def test_apply_refuses_monorepo_source_with_subpath(tmp_path: Path, monkeypatch):
    """apply() only records single-skill (repo-root) lock entries. A source
    carrying a subpath is a monorepo source, which apply() would silently
    mis-record as skillPath='SKILL.md' with no parentUrl. It must fail loud
    instead — the monorepo add path writes those entries, not apply()."""
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    src = ParsedSource(
        type="github",
        url="https://github.com/ajanderson1/personal_skills",
        owner_repo="ajanderson1/personal_skills",
        ref=None,
        subpath="aj-workflows/aj-flow",
    )
    plan = InstallPlan(
        slug="aj-flow", scope="global", source=src, ref=None,
        add_agents=(), remove_agents=(),
    )
    with pytest.raises(InstallError, match="monorepo source"):
        skill_install.apply(plan, home=None, project=None)


def test_uninstall_removes_canonical_and_symlinks(git_sandbox, tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    src = parse_source(str(git_sandbox.upstream))
    install(
        parsed=src, slug="demo", scope="project",
        home=None, project=project, harnesses=("claude",),
        env=git_sandbox.env,
    )
    uninstall(
        slug="demo", scope="project", home=None, project=project,
        harnesses=("claude",),
    )
    assert not (project / ".agents" / "skills" / "demo").exists()
    assert not (project / ".claude" / "skills" / "demo").exists()
