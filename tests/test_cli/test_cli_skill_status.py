from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_skill_status_clean(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])
    result = runner.invoke(main, ["skill", "status", "-g"])
    assert result.exit_code == 0
    assert "demo" in result.output
    assert "clean" in result.output


def test_skill_status_dirty(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo", "-g",
        "--harness", "claude",
    ])
    canonical = fake_home / ".agents" / "skills" / "demo"
    (canonical / "SKILL.md").write_text("self-edit\n")
    result = runner.invoke(main, ["skill", "status", "-g"])
    assert result.exit_code == 0
    assert "dirty" in result.output
