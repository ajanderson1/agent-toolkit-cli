"""Tests for surface aliases registered on the CLI.

Covers:
  - `ls` / `rm` subcommand aliases on the `skill` group (#169).
  - `skills` plural alias for the `skill` group itself (#180).

All exist to align with `npx -y skills` muscle memory.
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


def test_skills_group_help_matches_skill_group_help():
    """`skills --help` should resolve to the same group as `skill --help`."""
    runner = CliRunner()
    by_skill = runner.invoke(main, ["skill", "--help"])
    by_skills = runner.invoke(main, ["skills", "--help"])
    assert by_skill.exit_code == 0, by_skill.output
    assert by_skills.exit_code == 0, by_skills.output
    for verb in ("add", "install", "list", "ls", "remove", "rm", "status", "update", "push", "reset"):
        assert verb in by_skills.output, f"expected '{verb}' in `skills --help`"


def test_skills_list_behaves_like_skill_list(git_sandbox, tmp_path: Path, monkeypatch):
    """A representative subcommand invoked via the plural alias behaves identically."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.upstream).exit_code == 0

    by_skill = runner.invoke(main, ["skill", "list", "-g"])
    by_skills = runner.invoke(main, ["skills", "list", "-g"])
    assert by_skill.exit_code == 0, by_skill.output
    assert by_skills.exit_code == 0, by_skills.output
    assert by_skill.output == by_skills.output
    assert "demo" in by_skills.output


def test_root_help_lists_skills_as_canonical_command():
    """Root `--help` should advertise the plural canonical command only.

    Asserts the Commands block, not arbitrary prose -- the help text mentions
    `skills-lock.json` and 'manage skills' regardless of whether the command is
    wired, so a substring check would be a false positive.
    """
    import re
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0, result.output
    # Click renders each command as `  <name>  <description>`. Match name
    # followed by whitespace so `skill` doesn't slip in by being a prefix of `skills`.
    assert re.search(r"^\s+skills\s", result.output, re.MULTILINE), result.output
    assert not re.search(r"^\s+skill\s", result.output, re.MULTILINE), result.output
