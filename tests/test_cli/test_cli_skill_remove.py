import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_remove_clears_everything(git_sandbox, tmp_path: Path, monkeypatch):
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
    result = runner.invoke(main, ["skill", "remove", "demo", "-g"])
    assert result.exit_code == 0, result.output
    assert not (fake_home / ".agents" / "skills" / "demo").exists()
    assert not (fake_home / ".claude" / "skills" / "demo").exists()
    lock = json.loads((fake_home / ".agents" / ".skill-lock.json").read_text())
    assert "demo" not in lock["skills"]


def test_remove_refuses_dirty_without_force(
    git_sandbox, tmp_path: Path, monkeypatch,
):
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
    (canonical / "SKILL.md").write_text("uncommitted\n")
    result = runner.invoke(main, ["skill", "remove", "demo", "-g"])
    assert result.exit_code != 0
    assert "dirty" in result.output.lower()
    assert canonical.exists()


def test_remove_force_drops_dirty(git_sandbox, tmp_path: Path, monkeypatch):
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
    (canonical / "SKILL.md").write_text("uncommitted\n")
    result = runner.invoke(main, ["skill", "remove", "demo", "-g", "--force"])
    assert result.exit_code == 0, result.output
    assert not canonical.exists()
