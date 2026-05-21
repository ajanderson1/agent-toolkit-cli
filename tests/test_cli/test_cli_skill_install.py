"""Tests for `skill install` — agent-visibility symlinks from library.

v2.2: `skill install <slug> --agents AGENTS [--scope SCOPE]` creates symlinks
from agent locations to the library canonical.
"""
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _add_demo(runner, upstream_path, library_root):
    """Add demo skill to library, returning the invocation result."""
    return runner.invoke(main, [
        "skill", "add", str(upstream_path), "--slug", "demo",
    ])


# ── global scope ──────────────────────────────────────────────────────────


def test_install_global_universal_creates_agents_skills_symlink(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill install --agents universal at global scope creates ~/.agents/skills/<slug>."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    r = _add_demo(runner, git_sandbox.upstream, library_root)
    assert r.exit_code == 0, r.output

    result = runner.invoke(main, [
        "skill", "install", "demo", "--agents", "universal",
    ])
    assert result.exit_code == 0, result.output

    bundle_link = fake_home / ".agents" / "skills" / "demo"
    assert bundle_link.is_symlink(), "universal bundle symlink must be created"
    assert bundle_link.resolve() == (library_root / "demo").resolve()


def test_install_global_claude_code_creates_claude_symlink(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill install --agents claude-code at global scope creates ~/.claude/skills/<slug>."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))
    # Patch CLAUDE_HOME so the projection uses fake_home.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))

    from agent_toolkit_cli.skill_agents import AGENTS
    claude_agent = AGENTS["claude-code"]

    runner = CliRunner()
    r = _add_demo(runner, git_sandbox.upstream, library_root)
    assert r.exit_code == 0, r.output

    result = runner.invoke(main, [
        "skill", "install", "demo", "--agents", "claude-code",
    ])
    assert result.exit_code == 0, result.output

    claude_link = claude_agent.global_skills_dir / "demo"
    assert claude_link.is_symlink(), "claude-code symlink must be created"
    assert claude_link.resolve() == (library_root / "demo").resolve()
    claude_link.unlink()  # cleanup


def test_install_global_universal_and_claude_does_both(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill install --agents universal,claude-code creates both symlinks."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))

    from agent_toolkit_cli.skill_agents import AGENTS
    claude_agent = AGENTS["claude-code"]

    runner = CliRunner()
    r = _add_demo(runner, git_sandbox.upstream, library_root)
    assert r.exit_code == 0, r.output

    result = runner.invoke(main, [
        "skill", "install", "demo", "--agents", "universal,claude-code",
    ])
    assert result.exit_code == 0, result.output

    bundle_link = fake_home / ".agents" / "skills" / "demo"
    assert bundle_link.is_symlink()
    assert bundle_link.resolve() == (library_root / "demo").resolve()

    claude_link = claude_agent.global_skills_dir / "demo"
    assert claude_link.is_symlink()
    assert claude_link.resolve() == (library_root / "demo").resolve()
    claude_link.unlink()


def test_install_global_requires_library_entry(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill install fails if slug is not in the library."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    result = runner.invoke(main, [
        "skill", "install", "nonexistent", "--agents", "universal",
    ])
    assert result.exit_code != 0


def test_install_global_idempotent(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """Calling install twice for the same agent is idempotent."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    r = _add_demo(runner, git_sandbox.upstream, library_root)
    assert r.exit_code == 0, r.output

    r1 = runner.invoke(main, [
        "skill", "install", "demo", "--agents", "universal",
    ])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(main, [
        "skill", "install", "demo", "--agents", "universal",
    ])
    assert r2.exit_code == 0, r2.output

    bundle_link = fake_home / ".agents" / "skills" / "demo"
    assert bundle_link.is_symlink()


# ── project scope ─────────────────────────────────────────────────────────


def test_install_project_universal_clones_project_canonical(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill install --scope project --agents universal clones <project>/.agents/skills/<slug>."""
    library_root = tmp_path / "lib" / "skills"
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_demo(runner, git_sandbox.upstream, library_root)
    assert r.exit_code == 0, r.output

    result = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "universal",
    ])
    assert result.exit_code == 0, result.output

    project_canonical = project / ".agents" / "skills" / "demo"
    assert project_canonical.is_dir() and not project_canonical.is_symlink()
    assert (project_canonical / "SKILL.md").exists()


def test_install_project_non_universal_creates_symlink_when_dir_exists(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """Project install + claude-code + .claude/ present → symlink created."""
    library_root = tmp_path / "lib" / "skills"
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_demo(runner, git_sandbox.upstream, library_root)
    assert r.exit_code == 0, r.output

    result = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert result.exit_code == 0, result.output

    project_canonical = project / ".agents" / "skills" / "demo"
    claude_link = project / ".claude" / "skills" / "demo"
    assert project_canonical.is_dir()
    assert claude_link.is_symlink()
    assert claude_link.resolve() == project_canonical.resolve()


def test_install_project_non_universal_auto_creates_agent_root(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """Project install + windsurf + no .windsurf/ → agent root and symlink auto-created.

    v2.2: explicit --agents consent is sufficient; the directory is created on demand.
    """
    library_root = tmp_path / "lib" / "skills"
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = _add_demo(runner, git_sandbox.upstream, library_root)
    assert r.exit_code == 0, r.output

    result = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "windsurf",
    ])
    assert result.exit_code == 0, result.output

    windsurf_link = project / ".windsurf" / "skills" / "demo"
    assert windsurf_link.is_symlink(), ".windsurf/skills/demo symlink must be created"
    assert (project / ".windsurf").is_dir(), ".windsurf/ dir must be auto-created"


def test_install_agents_required():
    """skill install without --agents is an error."""
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "install", "demo"])
    assert result.exit_code != 0
    # click reports missing required option
    assert "agents" in result.output.lower() or "missing" in result.output.lower()
