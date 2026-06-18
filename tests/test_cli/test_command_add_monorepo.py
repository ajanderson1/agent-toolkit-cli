import json
import subprocess

from click.testing import CliRunner
from agent_toolkit_cli.cli import main


def test_command_add_monorepo_records_command_path(tmp_path, monkeypatch):
    env = {"GIT_AUTHOR_NAME":"T","GIT_AUTHOR_EMAIL":"t@example.invalid","GIT_COMMITTER_NAME":"T","GIT_COMMITTER_EMAIL":"t@example.invalid"}
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--initial-branch=main", str(repo)], check=True, env=env, capture_output=True)
    (repo / "cmds" / "demo").mkdir(parents=True)
    (repo / "cmds" / "demo" / "COMMAND.md").write_text("demo")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "seed"], check=True, env=env, capture_output=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    r = CliRunner().invoke(main, ["command", "add", f"file://{repo}/tree/main/cmds/demo"])
    assert r.exit_code == 0, r.output
    lock = json.loads((tmp_path / "home" / ".agent-toolkit" / "commands-lock.json").read_text())
    assert lock["skills"]["demo"]["commandPath"] == "cmds/demo/COMMAND.md"
