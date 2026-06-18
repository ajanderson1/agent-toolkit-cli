import subprocess
from pathlib import Path

from click.testing import CliRunner
from agent_toolkit_cli.cli import main


def _git(repo: Path, *args, env=None):
    subprocess.run(["git", "-C", str(repo), *args], check=True, env=env, capture_output=True)


def test_command_maintenance_verbs_are_invoked(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    import_file = tmp_path / "commands-lock.json"
    import_file.write_text('{"version": 1, "skills": {}}')

    env = {
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }

    # Create a bare upstream and a git-backed canonical for "demo" so
    # reset/update can fetch from origin.
    upstream = tmp_path / "upstream.git"
    _git(upstream.parent, "init", "--bare", "--initial-branch=main", str(upstream), env=env)
    demo_canonical = tmp_path / ".agent-toolkit" / "commands" / "demo"
    _git(tmp_path, "clone", str(upstream), str(demo_canonical), env=env)
    (demo_canonical / "COMMAND.md").write_text("demo")
    _git(demo_canonical, "add", "COMMAND.md", env=env)
    _git(demo_canonical, "commit", "-m", "init", env=env)
    _git(demo_canonical, "push", "origin", "main", env=env)

    lock_file = tmp_path / ".agent-toolkit" / "commands-lock.json"
    lock_file.write_text('{"version": 1, "skills": {"demo": {"source": "owner/repo", "sourceType": "github", "commandPath": "COMMAND.md"}}}')

    for args in [
        ["command", "list", "-g"],
        ["command", "ls", "-g"],
        ["command", "status", "-g"],
        ["command", "import", str(import_file), "-g"],
        ["command", "doctor", "-g"],
        ["command", "push", "-g"],
        ["command", "reset", "demo", "--force", "-g"],
        ["command", "remove", "demo", "-g"],
        ["command", "uninstall", "demo", "-g"],
        ["command", "update", "-g"],
    ]:
        result = runner.invoke(main, args)
        assert result.exit_code == 0, (args, result.output)
