from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _add_demo_project(runner, upstream_path, project):
    (project / ".claude").mkdir(exist_ok=True)
    return runner.invoke(main, [
        "--project", str(project),
        "skill", "add", str(upstream_path), "--slug", "demo", "-p",
        "--harness", "claude",
    ])


def test_skill_status_clean(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)

    runner = CliRunner()
    _add_demo_project(runner, git_sandbox.upstream, project)
    result = runner.invoke(main, [
        "--project", str(project), "skill", "status", "-p",
    ])
    assert result.exit_code == 0
    assert "demo" in result.output
    assert "clean" in result.output


def test_skill_status_dirty(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)

    runner = CliRunner()
    _add_demo_project(runner, git_sandbox.upstream, project)
    canonical = project / ".agents" / "skills" / "demo"
    (canonical / "SKILL.md").write_text("self-edit\n")
    result = runner.invoke(main, [
        "--project", str(project), "skill", "status", "-p",
    ])
    assert result.exit_code == 0
    assert "dirty" in result.output
