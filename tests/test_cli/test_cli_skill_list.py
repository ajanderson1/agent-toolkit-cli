from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _add_and_install_project(runner, upstream_path, project, library_root):
    """Add to library then install at project scope."""
    r = runner.invoke(main, [
        "skill", "add", str(upstream_path), "--slug", "demo",
    ])
    if r.exit_code != 0:
        return r
    return runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])


def test_skill_list_shows_added_skill(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    _add_and_install_project(runner, git_sandbox.upstream, project, library_root)
    result = runner.invoke(main, [
        "--project", str(project), "skill", "list", "-p",
    ])
    assert result.exit_code == 0, result.output
    assert "demo" in result.output


def test_skill_list_empty_when_no_lock(tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "list", "-g"])
    assert result.exit_code == 0
    assert "demo" not in result.output
