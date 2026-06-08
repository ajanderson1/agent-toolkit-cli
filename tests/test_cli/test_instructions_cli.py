"""CLI surface: `agent-toolkit-cli instructions <verb>` smoke."""
from __future__ import annotations

import json

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.instructions_adapters.symlink import PointerConflictError


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
    # Lock file is deleted when the last entry is removed (issue #312).
    assert not (project / "instructions-lock.json").exists()


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


# --- Global scope (BUG 1: home=None silently breaks global install) ---------


def _global_home(tmp_path, monkeypatch):
    """Point HOME at a tmp dir and seed the canonical global AGENTS.md.

    Path.home() reads $HOME, so this isolates every global path:
    the lock (~/.agent-toolkit/instructions-lock.json), the canonical
    (~/.agent-toolkit/AGENTS.md) and the pointer (~/.claude/CLAUDE.md).
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # Some platforms also read USERPROFILE; keep them aligned.
    monkeypatch.setenv("USERPROFILE", str(home))
    toolkit = home / ".agent-toolkit"
    toolkit.mkdir(parents=True)
    (toolkit / "AGENTS.md").write_text("# global canon\n")
    return home


def test_install_global_creates_pointer_and_truthful_lock(tmp_path, monkeypatch):
    """Global install MUST create the symlink, and the lock must only claim
    success when the symlink actually exists."""
    home = _global_home(tmp_path, monkeypatch)

    runner = CliRunner()
    result = runner.invoke(main, [
        "instructions", "install",
        "--scope", "global",
        "--harness", "claude-code",
    ])
    assert result.exit_code == 0, result.output

    pointer = home / ".claude" / "CLAUDE.md"
    assert pointer.is_symlink(), "global install did not create the pointer symlink"
    assert pointer.resolve() == (home / ".agent-toolkit" / "AGENTS.md").resolve()

    lock = json.loads((home / ".agent-toolkit" / "instructions-lock.json").read_text())
    assert lock["instructions"]["AGENTS.md"]["harnesses"] == ["claude-code"]
    assert lock["instructions"]["AGENTS.md"]["scope"] == "global"


def test_status_global_reports_ok(tmp_path, monkeypatch):
    _global_home(tmp_path, monkeypatch)

    runner = CliRunner()
    runner.invoke(main, [
        "instructions", "install", "--scope", "global", "--harness", "claude-code",
    ])

    result = runner.invoke(main, ["instructions", "status", "--scope", "global"])
    assert result.exit_code == 0, result.output
    assert "claude-code" in result.output
    assert "ok" in result.output.lower()


def test_doctor_global_clean(tmp_path, monkeypatch):
    _global_home(tmp_path, monkeypatch)

    runner = CliRunner()
    runner.invoke(main, [
        "instructions", "install", "--scope", "global", "--harness", "claude-code",
    ])

    result = runner.invoke(main, ["instructions", "doctor", "--scope", "global"])
    assert result.exit_code == 0, result.output
    assert "clean" in result.output.lower()


def test_uninstall_global_removes_pointer_and_clears_lock(tmp_path, monkeypatch):
    home = _global_home(tmp_path, monkeypatch)

    runner = CliRunner()
    runner.invoke(main, [
        "instructions", "install", "--scope", "global", "--harness", "claude-code",
    ])
    assert (home / ".claude" / "CLAUDE.md").is_symlink()

    result = runner.invoke(main, ["instructions", "uninstall", "--scope", "global"])
    assert result.exit_code == 0, result.output

    assert not (home / ".claude" / "CLAUDE.md").exists()
    # Lock file is deleted when the last entry is removed (issue #312).
    assert not (home / ".agent-toolkit" / "instructions-lock.json").exists()


# --- BUG 2: lock must not claim success if apply() fails --------------------


def test_install_failure_leaves_no_lock_entry(tmp_path, monkeypatch):
    """CanonicalMissingError must NOT leave a lock claiming the harness installed."""
    project = tmp_path / "proj"
    project.mkdir()
    # No AGENTS.md → apply() raises CanonicalMissingError.
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, [
        "instructions", "install", "--scope", "project", "--harness", "claude-code",
    ])
    assert result.exit_code != 0
    assert "AGENTS.md" in result.output

    lock_file = project / "instructions-lock.json"
    if lock_file.exists():
        lock = json.loads(lock_file.read_text())
        assert lock.get("instructions", {}) == {}, (
            "lock claims install succeeded even though apply() failed"
        )


def test_doctor_detects_unmanaged_claude_md(tmp_path, monkeypatch):
    """A real, lock-unrecorded CLAUDE.md is an 'unmanaged' finding (not 'clean')."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# my instructions\n")  # real file, no lock, no AGENTS.md
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project", "--no-fix"])
    assert result.exit_code != 0, result.output
    assert "unmanaged" in result.output.lower()
    assert "clean" not in result.output.lower()
    # --no-fix must not mutate.
    assert (project / "CLAUDE.md").is_file() and not (project / "CLAUDE.md").is_symlink()
    assert not (project / "AGENTS.md").exists()


def test_doctor_unmanaged_dedupes_shared_slot(tmp_path, monkeypatch):
    """augment + claude-code share the CLAUDE.md slot → exactly one unmanaged finding."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# x\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project", "--no-fix"])
    # Count "unmanaged:" with colon to avoid matching the pytest temp dir name.
    assert result.output.lower().count("unmanaged:") == 1, result.output


def test_doctor_adopt_renames_and_symlinks(tmp_path, monkeypatch):
    """`y` at the prompt: CLAUDE.md → AGENTS.md (content kept), CLAUDE.md becomes a symlink, lock written, re-run clean."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# my instructions\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code == 0, result.output  # adopted → nothing skipped

    agents = project / "AGENTS.md"
    pointer = project / "CLAUDE.md"
    assert agents.is_file() and agents.read_text() == "# my instructions\n"
    assert pointer.is_symlink() and pointer.resolve() == agents.resolve()

    lock = json.loads((project / "instructions-lock.json").read_text())
    assert "claude-code" in lock["instructions"]["AGENTS.md"]["harnesses"]

    # Round-trip: doctor is now clean.
    again = runner.invoke(main, ["instructions", "doctor", "--scope", "project"])
    assert again.exit_code == 0, again.output
    assert "clean" in again.output.lower()


def test_doctor_unmanaged_non_tty_does_not_mutate(tmp_path, monkeypatch):
    """No --no-fix, but no input available (non-TTY): finding reported, nothing adopted, exit 1."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# x\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    # No `input=` → click.prompt hits EOF → the except guard fires.
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"])
    assert result.exit_code != 0, result.output
    assert (project / "CLAUDE.md").is_file() and not (project / "CLAUDE.md").is_symlink()
    assert not (project / "AGENTS.md").exists()
    assert "no input available" in result.output.lower()


def test_doctor_unmanaged_does_not_clobber_existing_agents(tmp_path, monkeypatch):
    """Real CLAUDE.md + non-empty AGENTS.md: reported but report-only; 'y' must not destroy either."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# different\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    # Reported as unmanaged (real file, not in lock) but adopt is skipped → exit 1.
    assert result.exit_code != 0, result.output
    assert "unmanaged" in result.output.lower()
    # Neither file destroyed.
    assert (project / "AGENTS.md").read_text() == "# real canon\n"
    assert (project / "CLAUDE.md").read_text() == "# different\n"


def test_install_pointer_conflict_is_clean_clickexception(tmp_path, monkeypatch):
    """A real user file in the pointer slot yields a clean ClickException
    (not a raw traceback) and leaves the user's file intact."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    # User authored their own CLAUDE.md (a real file, not our symlink).
    (project / "CLAUDE.md").write_text("user authored\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, [
        "instructions", "install", "--scope", "project", "--harness", "claude-code",
    ])
    assert result.exit_code != 0
    # Clean ClickException — no raw traceback surfaced, no uncaught exception.
    assert "Traceback" not in result.output
    assert not isinstance(result.exception, PointerConflictError), (
        "PointerConflictError leaked as an uncaught traceback"
    )
    assert "real file" in result.output.lower() or "refused" in result.output.lower()

    # User's file untouched.
    assert (project / "CLAUDE.md").read_text() == "user authored\n"
    # Lock must not claim claude-code installed.
    lock_file = project / "instructions-lock.json"
    if lock_file.exists():
        lock = json.loads(lock_file.read_text())
        assert lock.get("instructions", {}) == {}
