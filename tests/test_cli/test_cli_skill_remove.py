"""Tests for `skill remove` — removes from library, not project scope.

v2.2: `skill remove <slug> [--force]` removes the library entry, all global
symlinks, and the lock entry. Project-scope canonicals are independent.
"""
import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _add_demo(runner, upstream_path, library_root):
    """Add demo skill to library."""
    return runner.invoke(main, [
        "skill", "add", str(upstream_path), "--slug", "demo",
    ])


def test_remove_clears_library_and_lock(git_sandbox, tmp_path: Path, monkeypatch):
    """skill remove deletes library dir and lock entry."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    _add_demo(runner, git_sandbox.upstream, library_root)
    assert (library_root / "demo").exists()

    result = runner.invoke(main, [
        "skill", "remove", "demo", "--force",
    ])
    assert result.exit_code == 0, result.output
    assert not (library_root / "demo").exists()

    lock_path = library_root.parent / "skills-lock.json"
    lock = json.loads(lock_path.read_text())
    assert "demo" not in lock["skills"]


def test_remove_without_force_skips_when_no_tty(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """Without --force, wizard fires; non-TTY returns None => skipped."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    _add_demo(runner, git_sandbox.upstream, library_root)
    library_dir = library_root / "demo"

    result = runner.invoke(main, [
        "skill", "remove", "demo",
    ])
    # Wizard returns None on non-TTY => "skipped" message, library intact.
    assert library_dir.exists()


def test_remove_force_drops_dirty(git_sandbox, tmp_path: Path, monkeypatch):
    """--force removes even a dirty library entry."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    _add_demo(runner, git_sandbox.upstream, library_root)
    library_dir = library_root / "demo"
    (library_dir / "SKILL.md").write_text("uncommitted\n")

    result = runner.invoke(main, [
        "skill", "remove", "demo", "--force",
    ])
    assert result.exit_code == 0, result.output
    assert not library_dir.exists()


def test_remove_not_in_library(git_sandbox, tmp_path: Path, monkeypatch):
    """Removing a slug not in the library emits a warning and exits 0."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    result = runner.invoke(main, [
        "skill", "remove", "nonexistent", "--force",
    ])
    assert result.exit_code == 0, result.output
    assert "not in library" in result.output
