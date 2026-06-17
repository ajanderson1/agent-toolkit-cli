import json
import subprocess
from pathlib import Path

from click.testing import CliRunner
from agent_toolkit_cli.cli import main


def _write_command_repo(path: Path, env: dict[str, str], body: str = "# Demo\n$ARGUMENTS\n") -> None:
    (path / "COMMAND.md").write_text(body)
    subprocess.run(["git", "-C", str(path), "add", "COMMAND.md"], check=True, env=env, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "command"], check=True, env=env, capture_output=True)
    subprocess.run(["git", "-C", str(path), "push", "origin", "main"], check=True, env=env, capture_output=True)


def test_command_add_requires_command_md(git_sandbox, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    runner = CliRunner()
    result = runner.invoke(main, ["command", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert result.exit_code != 0
    assert "COMMAND.md" in result.output


def test_command_add_writes_lock_and_install_defaults(git_sandbox, tmp_path, monkeypatch):
    _write_command_repo(git_sandbox.clone, git_sandbox.env)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    runner = CliRunner()
    result = runner.invoke(main, ["command", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert result.exit_code == 0, result.output
    lock = json.loads((tmp_path / "home" / ".agent-toolkit" / "commands-lock.json").read_text())
    assert lock["skills"]["demo"]["commandPath"] == "COMMAND.md"
    install = runner.invoke(main, ["command", "install", "demo", "-g"])
    assert install.exit_code == 0, install.output
    assert (tmp_path / "home" / ".claude" / "commands" / "demo.md").is_symlink()
    assert (tmp_path / "home" / ".pi" / "agent" / "prompts" / "demo.md").is_symlink()
    assert (tmp_path / "home" / ".gemini" / "commands" / "demo.toml").exists()


def test_command_add_rejects_path_slug(git_sandbox, tmp_path, monkeypatch):
    _write_command_repo(git_sandbox.clone, git_sandbox.env)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    result = CliRunner().invoke(main, ["command", "add", str(git_sandbox.upstream), "--slug", "../bad"])
    assert result.exit_code != 0
    assert "invalid command slug" in result.output
