"""Tests for `skill add` — library-only clone, no symlinks.

v2.2: `skill add <source> [--slug ...] [--ref ...]` clones into the library
and writes the global lock. No symlinks are created.
"""
import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_skill_add_creates_library_entry_and_no_symlinks(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill add clones to library and writes global lock. No symlinks."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    result = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream),
        "--slug", "demo",
    ])
    assert result.exit_code == 0, result.output

    library_dir = library_root / "demo"
    assert (library_dir / "SKILL.md").exists(), "library dir should be cloned"

    # No symlinks at ~/.agents/skills/demo or ~/.claude/skills/demo.
    agents_link = Path.home() / ".agents" / "skills" / "demo"
    claude_link = Path.home() / ".claude" / "skills" / "demo"
    assert not agents_link.exists(), "add must not create ~/.agents/skills symlink"
    assert not claude_link.exists(), "add must not create ~/.claude/skills symlink"

    lock_path = library_root.parent / "skills-lock.json"
    assert lock_path.exists(), "global lock should be written"
    lock = json.loads(lock_path.read_text())
    assert "demo" in lock["skills"]
    entry = lock["skills"]["demo"]
    assert entry["source"] == str(git_sandbox.upstream)
    assert entry["sourceType"] in {"git", "local"}


def test_skill_add_source_refuses_complete_batch_on_conflict(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """A later collision must not publish earlier siblings or rewrite records."""
    repo = git_sandbox.clone
    skills = repo / "skills"
    (skills / "alpha").mkdir(parents=True)
    (repo / "SKILL.md").unlink()
    (skills / "alpha" / "SKILL.md").write_text("---\nname: Alpha\n---\n")
    (skills / "beta").mkdir()
    (skills / "beta" / "SKILL.md").write_text("---\nname: Beta\n---\n")
    subprocess.run(
        ["git", "-C", str(repo), "add", "-A"],
        check=True, env=git_sandbox.env,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "Add skills"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "push", "origin", "main"],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    library_root = tmp_path / "lib" / "skills"
    for key, value in git_sandbox.env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    existing = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "alpha",
    ])
    assert existing.exit_code == 0, existing.output
    from agent_toolkit_cli.skill_lock import read_lock, write_lock
    from agent_toolkit_cli.skill_paths import library_lock_path
    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    lock.skills["alpha"].source = "different/repo"
    write_lock(lock_path, lock)

    from agent_toolkit_cli.commands import skill as skill_commands
    from agent_toolkit_cli.skill_source import ParsedSource
    monkeypatch.setattr(
        skill_commands, "parse_source",
        lambda _: ParsedSource(
            type="git", url=str(git_sandbox.upstream), owner_repo="owner/repo",
            ref=None, subpath=None, skill_name=None,
        ),
    )
    result = runner.invoke(main, ["skill", "add", "--source", "owner/repo"])
    assert result.exit_code != 0
    assert "collision" in result.output
    lock = read_lock(lock_path)
    assert set(lock.skills) == {"alpha"}
    assert lock.skills["alpha"].source == "different/repo"
    assert not (library_root / "beta").exists()


def test_skill_add_is_non_interactive(git_sandbox, tmp_path: Path, monkeypatch):
    """skill add completes without any interactive prompts."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    result = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ], input="")
    # Non-interactive: should succeed without blocking on input.
    assert result.exit_code == 0, result.output


def test_skill_add_no_agent_flag(git_sandbox, tmp_path: Path, monkeypatch):
    """--agent flag no longer exists on skill add."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    result = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream),
        "--slug", "demo", "--agent", "claude-code",
    ])
    assert result.exit_code != 0
    assert "no such option" in result.output.lower() or "Error" in result.output


def test_skill_add_idempotent_same_source(git_sandbox, tmp_path: Path, monkeypatch):
    """Adding the same source twice doesn't error (skips reclone)."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r1 = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(main, [
        "skill", "add", str(git_sandbox.upstream), "--slug", "demo",
    ])
    assert r2.exit_code == 0, r2.output
