"""Tests for `skill import` — additive cross-machine library sync."""
import json
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_reconstruct_helper_clones_single_repo_and_pins(
    git_sandbox, tmp_path, monkeypatch
):
    """reconstruct_skill_into_library clones a single repo and honours pin_sha."""
    from agent_toolkit_cli import skill_git
    from agent_toolkit_cli.commands.skill import reconstruct_skill_into_library
    from agent_toolkit_cli.skill_paths import library_skill_path
    from agent_toolkit_cli.skill_source import parse_source

    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    parsed = parse_source(str(git_sandbox.upstream))
    target_sha = skill_git.head_sha(git_sandbox.clone, env=None)

    upstream_sha, local_sha = reconstruct_skill_into_library(
        parsed, "demo", pin_sha=target_sha,
    )

    assert (library_skill_path("demo") / "SKILL.md").exists()
    assert local_sha == target_sha


NOTE_UPSTREAM = "pinned to upstream commits"
NOTE_PROJECT = "Project-scoped skills"
NOTE_AGENTS = "not installed for any agent"


def test_import_missing_file_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(tmp_path / "nope.json")])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_import_empty_file_imports_nothing_but_prints_notes(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    incoming = tmp_path / "incoming.json"
    incoming.write_text('{"version": 1, "skills": {}}')
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "0 added" in result.output
    assert NOTE_UPSTREAM in result.output
    assert NOTE_PROJECT in result.output
    assert NOTE_AGENTS in result.output
