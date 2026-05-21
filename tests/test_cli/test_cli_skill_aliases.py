"""Tests for the `ls` / `rm` aliases registered on the `skill` group.

Surface alignment with `npx -y skills` — see #169.
"""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _add_demo(runner: CliRunner, upstream_path: Path, slug: str = "demo"):
    return runner.invoke(main, [
        "skill", "add", str(upstream_path), "--slug", slug,
    ])


def test_skill_ls_is_list(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.upstream).exit_code == 0

    by_list = runner.invoke(main, ["skill", "list", "-g"])
    by_ls = runner.invoke(main, ["skill", "ls", "-g"])
    assert by_list.exit_code == 0, by_list.output
    assert by_ls.exit_code == 0, by_ls.output
    assert by_list.output == by_ls.output
    assert "demo" in by_ls.output


def test_skill_ls_supports_json_flag(git_sandbox, tmp_path: Path, monkeypatch):
    """The `ls` alias shares list_cmd's callback so --json works through it too."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.upstream).exit_code == 0

    result = runner.invoke(main, ["skill", "ls", "-g", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert [obj["slug"] for obj in data] == ["demo"]


def test_skill_rm_is_remove(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.upstream).exit_code == 0
    assert (library_root / "demo").exists()

    result = runner.invoke(main, ["skill", "rm", "demo", "--force"])
    assert result.exit_code == 0, result.output
    assert not (library_root / "demo").exists()

    lock_path = library_root.parent / "skills-lock.json"
    lock = json.loads(lock_path.read_text())
    assert "demo" not in lock["skills"]


def test_skill_group_help_lists_aliases():
    """Both `ls` and `rm` should appear in `skill --help` output."""
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "--help"])
    assert result.exit_code == 0, result.output
    for verb in ("list", "ls", "remove", "rm"):
        assert verb in result.output, f"expected '{verb}' in skill --help"
