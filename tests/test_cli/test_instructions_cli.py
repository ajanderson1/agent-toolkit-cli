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


def test_list_shows_verdict_per_harness():
    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "list"])
    assert result.exit_code == 0, result.output

    # Spot-check: must include the 7 symlink-verdict harnesses and at least
    # one native and one gap harness.
    for h in ("claude-code", "gemini-cli", "codex", "continue"):
        assert h in result.output, f"missing {h} in output"
    assert "symlink" in result.output
    assert "native" in result.output


def test_list_json_format():
    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "list", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    by_harness = {row["harness"]: row for row in data}
    assert by_harness["claude-code"]["verdict"] == "symlink"
    assert by_harness["codex"]["verdict"] == "native"


def test_status_reports_present_and_missing(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    runner.invoke(main, ["instructions", "install", "--scope", "project", "--harness", "claude-code"])

    # Remove the pointer to simulate drift.
    (project / "CLAUDE.md").unlink()

    result = runner.invoke(main, ["instructions", "status", "--scope", "project"])
    assert result.exit_code == 0
    assert "claude-code" in result.output
    assert "missing" in result.output.lower()


def test_status_reports_conflict_when_pointer_points_elsewhere(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    (project / "OTHER.md").write_text("other\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    runner.invoke(main, ["instructions", "install", "--scope", "project", "--harness", "claude-code"])

    # Replace our symlink with one pointing at OTHER.md.
    (project / "CLAUDE.md").unlink()
    (project / "CLAUDE.md").symlink_to(project / "OTHER.md")

    result = runner.invoke(main, ["instructions", "status", "--scope", "project"])
    assert "conflict" in result.output.lower()


def test_doctor_reports_orphan_pointer_when_canonical_gone(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    runner.invoke(main, ["instructions", "install", "--scope", "project", "--harness", "claude-code"])
    (project / "AGENTS.md").unlink()  # canonical gone; pointer dangles

    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"])
    assert result.exit_code != 0
    assert "orphan" in result.output.lower()


def test_doctor_clean_exit_zero(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    runner.invoke(main, ["instructions", "install", "--scope", "project", "--harness", "claude-code"])

    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"])
    assert result.exit_code == 0, result.output
    assert "clean" in result.output.lower()


def test_doctor_reports_conflict(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    runner.invoke(main, ["instructions", "install", "--scope", "project", "--harness", "claude-code"])
    # Replace symlink with a real file.
    (project / "CLAUDE.md").unlink()
    (project / "CLAUDE.md").write_text("user authored\n")

    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"])
    assert result.exit_code != 0
    assert "conflict" in result.output.lower()
