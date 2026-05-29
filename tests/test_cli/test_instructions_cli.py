"""CLI surface: `agent-toolkit-cli instructions <verb>` smoke."""
from __future__ import annotations

import json

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_instructions_group_registered():
    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "--help"])
    assert result.exit_code == 0, result.output
    assert "install" in result.output
    assert "uninstall" in result.output
    assert "list" in result.output
    assert "status" in result.output
    assert "doctor" in result.output


def test_install_creates_pointer_for_named_harness(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, [
        "instructions", "install",
        "--scope", "project",
        "--harness", "claude-code",
    ])
    assert result.exit_code == 0, result.output

    pointer = project / "CLAUDE.md"
    assert pointer.is_symlink()

    lock = json.loads((project / "instructions-lock.json").read_text())
    assert lock["instructions"]["AGENTS.md"]["harnesses"] == ["claude-code"]


def test_install_refuses_when_canonical_missing(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    # No AGENTS.md.
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, [
        "instructions", "install",
        "--scope", "project",
        "--harness", "claude-code",
    ])
    assert result.exit_code != 0
    assert "AGENTS.md" in result.output


def test_install_rejects_native_harness_with_clear_message(tmp_path, monkeypatch):
    """`codex` is `native` — no pointer needed. CLI should refuse explicitly."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, [
        "instructions", "install",
        "--scope", "project",
        "--harness", "codex",
    ])
    assert result.exit_code != 0
    assert "native" in result.output.lower()
    assert "no pointer needed" in result.output.lower()


def test_install_all_default_targets_all_symlink_harnesses(tmp_path, monkeypatch):
    """No --harness flag → install for every symlink-verdict harness."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "install", "--scope", "project"])
    assert result.exit_code == 0, result.output

    # All project-slot symlink cells should be pointers now.
    from agent_toolkit_cli.instructions_adapters.symlink import CELLS
    for harness, cell in CELLS.items():
        if cell["project"]:
            pointer_name = cell["pointer_name"]
            assert (project / pointer_name).is_symlink(), f"missing pointer: {harness} → {pointer_name}"


def test_uninstall_removes_pointers_and_clears_lock(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    runner.invoke(main, ["instructions", "install", "--scope", "project", "--harness", "claude-code"])
    assert (project / "CLAUDE.md").is_symlink()

    result = runner.invoke(main, ["instructions", "uninstall", "--scope", "project"])
    assert result.exit_code == 0, result.output

    assert not (project / "CLAUDE.md").exists()
    lock = json.loads((project / "instructions-lock.json").read_text())
    assert lock["instructions"] == {}


def test_uninstall_leaves_foreign_files_alone(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    # User has authored their own CLAUDE.md.
    (project / "CLAUDE.md").write_text("user authored\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "uninstall", "--scope", "project"])
    # No lock entry to clear, no symlink to remove — exits cleanly.
    assert result.exit_code == 0

    assert (project / "CLAUDE.md").read_text() == "user authored\n"
