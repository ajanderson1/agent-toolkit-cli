import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_skill_add_project_writes_lock_and_creates_symlinks(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """Project-scope add writes canonical + per-agent symlinks.

    Switched from global scope: global-scope agent projections now resolve via
    cfg.global_skills_dir (real ~/.claude etc.), which would pollute the
    developer's machine during tests.
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()  # satisfy non-universal skip-rule
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)

    runner = CliRunner()
    result = runner.invoke(main, [
        "--project", str(project),
        "skill", "add", str(git_sandbox.upstream),
        "--slug", "demo", "-p",
        "--harness", "claude",
    ])
    assert result.exit_code == 0, result.output

    canonical = project / ".agents" / "skills" / "demo"
    assert (canonical / "SKILL.md").exists()
    assert (project / ".claude" / "skills" / "demo").is_symlink()

    lock = json.loads((project / "skills-lock.json").read_text())
    assert lock["version"] == 1
    assert "demo" in lock["skills"]
    entry = lock["skills"]["demo"]
    assert entry["source"] == str(git_sandbox.upstream)
    assert entry["sourceType"] in {"git", "local"}
    assert entry["upstreamSha"] and entry["localSha"]


def test_skill_add_global_writes_lock_and_canonical(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """Global-scope add writes canonical + lock; no harness symlinks checked.

    The canonical location (fake_home/.agents/skills/demo) is correct.
    Per-agent projections for non-universal agents use cfg.global_skills_dir
    (resolved at import time), so we don't assert their location here.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    # Use codex only (universal → skipped at global scope, no real fs write).
    result = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream),
        "--slug", "demo", "-g",
        "--harness", "codex",
    ])
    assert result.exit_code == 0, result.output

    canonical = fake_home / ".agents" / "skills" / "demo"
    assert (canonical / "SKILL.md").exists()

    lock = json.loads((fake_home / ".agents" / ".skill-lock.json").read_text())
    assert lock["version"] == 1
    assert "demo" in lock["skills"]
    entry = lock["skills"]["demo"]
    assert entry["source"] == str(git_sandbox.upstream)
    assert entry["sourceType"] in {"git", "local"}
    assert entry["upstreamSha"] and entry["localSha"]
