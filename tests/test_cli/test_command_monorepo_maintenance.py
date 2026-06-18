import json
import subprocess
from pathlib import Path

from click.testing import CliRunner
from agent_toolkit_cli.cli import main


def _setup_monorepo(tmp_path: Path, env: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--initial-branch=main", str(repo)], check=True, env=env, capture_output=True)
    (repo / "cmds" / "demo").mkdir(parents=True)
    (repo / "cmds" / "demo" / "COMMAND.md").write_text("demo v1")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "seed"], check=True, env=env, capture_output=True)
    return repo


def _advance_monorepo(repo: Path, env: dict[str, str]) -> None:
    (repo / "cmds" / "demo" / "COMMAND.md").write_text("demo v2")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "update"], check=True, env=env, capture_output=True)


def test_command_update_advances_monorepo_parent_and_refreshes_lock(tmp_path, monkeypatch):
    env = {
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    repo = _setup_monorepo(tmp_path, env)
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()

    add = runner.invoke(main, ["command", "add", f"file://{repo}/tree/main/cmds/demo", "--slug", "demo"])
    assert add.exit_code == 0, add.output

    before_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True, env=env, capture_output=True, text=True,
    ).stdout.strip()

    _advance_monorepo(repo, env)

    update = runner.invoke(main, ["command", "update", "demo", "-g"])
    assert update.exit_code == 0, update.output

    lock = json.loads((home / ".agent-toolkit" / "commands-lock.json").read_text())
    entry = lock["skills"]["demo"]
    assert entry["localSha"] != before_sha
    assert entry["upstreamSha"] != before_sha
    assert entry["commandPath"] == "cmds/demo/COMMAND.md"


def test_command_reset_advances_monorepo_parent_and_refreshes_lock(tmp_path, monkeypatch):
    env = {
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    repo = _setup_monorepo(tmp_path, env)
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()

    add = runner.invoke(main, ["command", "add", f"file://{repo}/tree/main/cmds/demo", "--slug", "demo"])
    assert add.exit_code == 0, add.output

    before_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True, env=env, capture_output=True, text=True,
    ).stdout.strip()

    _advance_monorepo(repo, env)

    reset = runner.invoke(main, ["command", "reset", "demo", "--force", "-g"])
    assert reset.exit_code == 0, reset.output

    lock = json.loads((home / ".agent-toolkit" / "commands-lock.json").read_text())
    entry = lock["skills"]["demo"]
    assert entry["localSha"] != before_sha
    assert entry["upstreamSha"] != before_sha
