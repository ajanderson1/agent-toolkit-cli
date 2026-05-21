import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_skill_add_global_writes_lock_and_creates_symlinks(
    git_sandbox, tmp_path: Path, monkeypatch
):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    result = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream),
        "--slug", "demo", "-g",
        "--harness", "claude", "--harness", "codex",
    ])
    assert result.exit_code == 0, result.output

    canonical = fake_home / ".agents" / "skills" / "demo"
    assert (canonical / "SKILL.md").exists()
    assert (fake_home / ".claude" / "skills" / "demo").is_symlink()
    assert (fake_home / ".codex" / "skills" / "demo").is_symlink()

    lock = json.loads((fake_home / ".agents" / ".skill-lock.json").read_text())
    assert lock["version"] == 1
    assert "demo" in lock["skills"]
    entry = lock["skills"]["demo"]
    assert entry["source"] == str(git_sandbox.upstream)
    assert entry["sourceType"] in {"git", "local"}
    assert entry["upstreamSha"] and entry["localSha"]
