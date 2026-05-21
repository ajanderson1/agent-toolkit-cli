import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _add_demo_project(runner, upstream_path, project):
    """Add demo skill at project scope with claude harness."""
    (project / ".claude").mkdir(exist_ok=True)
    return runner.invoke(main, [
        "--project", str(project),
        "skill", "add", str(upstream_path), "--slug", "demo", "-p",
        "--harness", "claude",
    ])


def test_remove_clears_everything(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)

    runner = CliRunner()
    _add_demo_project(runner, git_sandbox.upstream, project)
    result = runner.invoke(main, [
        "--project", str(project), "skill", "remove", "demo", "-p",
    ])
    assert result.exit_code == 0, result.output
    assert not (project / ".agents" / "skills" / "demo").exists()
    assert not (project / ".claude" / "skills" / "demo").exists()
    lock = json.loads((project / "skills-lock.json").read_text())
    assert "demo" not in lock["skills"]


def test_remove_refuses_dirty_without_force(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)

    runner = CliRunner()
    _add_demo_project(runner, git_sandbox.upstream, project)
    canonical = project / ".agents" / "skills" / "demo"
    (canonical / "SKILL.md").write_text("uncommitted\n")
    result = runner.invoke(main, [
        "--project", str(project), "skill", "remove", "demo", "-p",
    ])
    assert result.exit_code != 0
    assert "dirty" in result.output.lower()
    assert canonical.exists()


def test_remove_force_drops_dirty(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)

    runner = CliRunner()
    _add_demo_project(runner, git_sandbox.upstream, project)
    canonical = project / ".agents" / "skills" / "demo"
    (canonical / "SKILL.md").write_text("uncommitted\n")
    result = runner.invoke(main, [
        "--project", str(project), "skill", "remove", "demo", "-p", "--force",
    ])
    assert result.exit_code == 0, result.output
    assert not canonical.exists()
