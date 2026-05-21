"""Tests for `skill uninstall` — removes symlinks, library untouched.

v2.2: `skill uninstall <slug> --agents AGENTS [--scope SCOPE]` removes
agent-visibility symlinks without touching the library canonical.
"""
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _add_and_install_global_universal(runner, upstream_path, library_root, fake_home):
    """Add to library then install universal bundle at global scope."""
    r = runner.invoke(main, [
        "skill", "add", str(upstream_path), "--slug", "demo",
    ])
    if r.exit_code != 0:
        return r
    return runner.invoke(main, [
        "skill", "install", "demo", "--agents", "universal",
    ])


def test_uninstall_global_universal_removes_symlink(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill uninstall --agents universal removes ~/.agents/skills/<slug>."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    r = _add_and_install_global_universal(
        runner, git_sandbox.upstream, library_root, fake_home
    )
    assert r.exit_code == 0, r.output

    bundle_link = fake_home / ".agents" / "skills" / "demo"
    assert bundle_link.is_symlink()

    result = runner.invoke(main, [
        "skill", "uninstall", "demo", "--agents", "universal",
    ])
    assert result.exit_code == 0, result.output
    assert not bundle_link.exists(), "symlink must be removed"

    # Library canonical untouched.
    assert (library_root / "demo").exists(), "library must be untouched"


def test_uninstall_idempotent(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """Uninstalling an agent that isn't installed is a no-op."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    r = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert r.exit_code == 0, r.output

    # Uninstall without having installed first.
    result = runner.invoke(main, [
        "skill", "uninstall", "demo", "--agents", "universal",
    ])
    assert result.exit_code == 0, result.output


def test_uninstall_project_preserves_canonical(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill uninstall --scope project removes symlinks but preserves project canonical."""
    library_root = tmp_path / "lib" / "skills"
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert r.exit_code == 0, r.output

    project_canonical = project / ".agents" / "skills" / "demo"
    claude_link = project / ".claude" / "skills" / "demo"
    assert project_canonical.is_dir()
    assert claude_link.is_symlink()

    result = runner.invoke(main, [
        "--project", str(project),
        "skill", "uninstall", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert result.exit_code == 0, result.output
    assert not claude_link.exists(), "claude-code symlink must be removed"
    assert project_canonical.is_dir(), "project canonical must be preserved"


def test_uninstall_agents_required():
    """skill uninstall without --agents is an error."""
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "uninstall", "demo"])
    assert result.exit_code != 0
    assert "agents" in result.output.lower() or "missing" in result.output.lower()
