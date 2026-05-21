from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_skill_list_shows_added_skill(git_sandbox, tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)

    runner = CliRunner()
    runner.invoke(main, [
        "--project", str(project),
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-p",
        "--harness", "claude",
    ])
    result = runner.invoke(main, [
        "--project", str(project), "skill", "list", "-p",
    ])
    assert result.exit_code == 0, result.output
    assert "demo" in result.output


def test_skill_list_empty_when_no_lock(tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "empty-home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "list", "-g"])
    assert result.exit_code == 0
    assert "demo" not in result.output
