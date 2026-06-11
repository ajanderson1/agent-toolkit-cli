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


def test_doctor_backup_fix_decline_keeps_finding(tmp_path, monkeypatch):
    """Real CLAUDE.md + populated AGENTS.md: 'N' leaves everything untouched,
    the finding stays reported, exit 1 (AC6)."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# different\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="N\n")
    assert result.exit_code != 0, result.output
    assert "unmanaged" in result.output.lower()
    assert (project / "AGENTS.md").read_text() == "# real canon\n"
    claude = project / "CLAUDE.md"
    assert claude.is_file() and not claude.is_symlink()
    assert claude.read_text() == "# different\n"
    assert not (project / "CLAUDE.md.pre-adopt.bak").exists()


def test_doctor_adopt_global(tmp_path, monkeypatch):
    home = _global_home(tmp_path, monkeypatch)
    # _global_home seeds ~/.agent-toolkit/AGENTS.md — remove it so adoption is unambiguous.
    (home / ".agent-toolkit" / "AGENTS.md").unlink()
    # Real, unmanaged file at the global claude-code slot.
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "CLAUDE.md").write_text("# global instructions\n")

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "global"], input="y\n")
    assert result.exit_code == 0, result.output

    agents = home / ".agent-toolkit" / "AGENTS.md"
    pointer = home / ".claude" / "CLAUDE.md"
    assert agents.is_file() and agents.read_text() == "# global instructions\n"
    assert pointer.is_symlink() and pointer.resolve() == agents.resolve()

    again = runner.invoke(main, ["instructions", "doctor", "--scope", "global"])
    assert again.exit_code == 0, again.output
    assert "clean" in again.output.lower()


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


# --- #337 adopt rollback + slot-correctness regressions -----------------------


def test_doctor_adopt_rolls_back_on_apply_failure(tmp_path, monkeypatch):
    """If install.apply() raises *any* error mid-adopt, the user's file and the
    lock are fully restored — no lying lock, no moved file (review finding 2)."""
    import agent_toolkit_cli.instructions_install as install_mod

    project = tmp_path / "proj"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# mine\n")
    monkeypatch.chdir(project)

    # Force apply() to blow up with a non-domain error after the rename+lock write.
    # doctor_cmd calls `instructions_install.apply(...)` via the module, so
    # patching the source module's attribute reaches the same call.
    def boom(*a, **k):
        raise OSError("disk gone")

    monkeypatch.setattr(install_mod, "apply", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code != 0, result.output
    assert "adopt failed" in result.output.lower()

    # Fully rolled back: real file restored, AGENTS.md gone, no lock entry.
    pointer = project / "CLAUDE.md"
    assert pointer.is_file() and not pointer.is_symlink()
    assert pointer.read_text() == "# mine\n"
    assert not (project / "AGENTS.md").exists()
    lock_file = project / "instructions-lock.json"
    if lock_file.exists():
        lock = json.loads(lock_file.read_text())
        assert lock.get("instructions", {}) == {}, "lock claims an adopt that was rolled back"


def test_doctor_adopt_rolls_back_partial_apply_with_prior_lock(tmp_path, monkeypatch):
    """apply() that creates our slot's symlink then raises on a *different* wanted
    slot must leave the original real file restored and the prior lock intact —
    not a half-adopted state (review finding 1)."""
    import agent_toolkit_cli.instructions_install as install_mod

    project = tmp_path / "proj"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# mine\n")
    # A pre-existing, unrelated lock entry (so prior_existed is True and there is
    # a prior state to restore to).
    (project / "instructions-lock.json").write_text(json.dumps({
        "version": 1,
        "instructions": {"AGENTS.md": {
            "scope": "project", "source": "AGENTS.md", "harnesses": ["gemini-cli"],
        }},
    }))
    monkeypatch.chdir(project)

    def apply_then_fail(*a, **k):
        # Simulate apply() laying our symlink down, then failing on another slot.
        canonical = project / "AGENTS.md"
        (project / "CLAUDE.md").symlink_to(canonical)
        raise install_mod.CanonicalMissingError("boom on other slot")

    monkeypatch.setattr(install_mod, "apply", apply_then_fail)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code != 0, result.output

    # The symlink apply() created must be gone; the real file must be back.
    pointer = project / "CLAUDE.md"
    assert pointer.is_file() and not pointer.is_symlink(), "symlink not cleaned up on rollback"
    assert pointer.read_text() == "# mine\n"
    assert not (project / "AGENTS.md").exists()
    # Prior lock restored verbatim — claude-code never recorded.
    lock = json.loads((project / "instructions-lock.json").read_text())
    assert lock["instructions"]["AGENTS.md"]["harnesses"] == ["gemini-cli"]


def test_doctor_adopts_augment_global_slot_as_augment_not_claude(tmp_path, monkeypatch):
    """At global scope ~/.augment/CLAUDE.md is augment's OWN slot, distinct from
    ~/.claude/CLAUDE.md. Adopting it must record augment and symlink the augment
    slot — never fabricate a claude-code pointer (review finding 3)."""
    home = _global_home(tmp_path, monkeypatch)
    (home / ".agent-toolkit" / "AGENTS.md").unlink()  # make adoption unambiguous
    augment_slot = home / ".augment" / "CLAUDE.md"
    augment_slot.parent.mkdir(parents=True, exist_ok=True)
    augment_slot.write_text("# augment instructions\n")

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "global"], input="y\n")
    assert result.exit_code == 0, result.output

    agents = home / ".agent-toolkit" / "AGENTS.md"
    assert agents.read_text() == "# augment instructions\n"
    # augment's slot is now the symlink; claude-code's slot was NOT fabricated.
    assert augment_slot.is_symlink() and augment_slot.resolve() == agents.resolve()
    assert not (home / ".claude" / "CLAUDE.md").exists(), "fabricated an unrelated claude-code pointer"

    lock = json.loads((home / ".agent-toolkit" / "instructions-lock.json").read_text())
    assert lock["instructions"]["AGENTS.md"]["harnesses"] == ["augment"]


# --- #375 backup-then-symlink fix (canonical already populated) ----------------


def test_doctor_backup_fix_renames_to_bak_and_symlinks(tmp_path, monkeypatch):
    """Populated AGENTS.md + unmanaged CLAUDE.md: 'y' backs the file up to
    CLAUDE.md.pre-adopt.bak, symlinks the slot at canonical, merges the lock,
    and doctor is clean on re-run. Content is never merged or destroyed."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# different\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code == 0, result.output

    agents = project / "AGENTS.md"
    pointer = project / "CLAUDE.md"
    backup = project / "CLAUDE.md.pre-adopt.bak"
    assert agents.read_text() == "# real canon\n"  # canonical untouched
    assert backup.is_file() and backup.read_text() == "# different\n"
    assert pointer.is_symlink() and pointer.resolve() == agents.resolve()
    # Output points the user at the backup (manual content reconciliation).
    assert "pre-adopt.bak" in result.output

    lock = json.loads((project / "instructions-lock.json").read_text())
    assert "claude-code" in lock["instructions"]["AGENTS.md"]["harnesses"]

    again = runner.invoke(main, ["instructions", "doctor", "--scope", "project"])
    assert again.exit_code == 0, again.output
    assert "clean" in again.output.lower()


def test_doctor_backup_fix_fails_loudly_on_existing_bak(tmp_path, monkeypatch):
    """A pre-existing CLAUDE.md.pre-adopt.bak: the fix refuses, nothing changes
    (never clobber, never silently discard — AC3)."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# mine\n")
    (project / "CLAUDE.md.pre-adopt.bak").write_text("# old backup\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code != 0, result.output
    assert "already exists" in result.output.lower()

    # Nothing changed.
    claude = project / "CLAUDE.md"
    assert claude.is_file() and not claude.is_symlink()
    assert claude.read_text() == "# mine\n"
    assert (project / "CLAUDE.md.pre-adopt.bak").read_text() == "# old backup\n"
    assert (project / "AGENTS.md").read_text() == "# real canon\n"
    lock_file = project / "instructions-lock.json"
    if lock_file.exists():
        lock = json.loads(lock_file.read_text())
        assert lock.get("instructions", {}) == {}


def test_doctor_backup_fix_rolls_back_on_apply_failure(tmp_path, monkeypatch):
    """If install.apply() raises ANY error mid-fix, the user's file comes back
    from the .bak, the .bak is gone, canonical untouched, no lock entry (AC4)."""
    import agent_toolkit_cli.instructions_install as install_mod

    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# mine\n")
    monkeypatch.chdir(project)

    def boom(*a, **k):
        raise OSError("disk gone")

    # doctor_cmd calls instructions_install.apply via the module attribute —
    # patch the source module (Click re-exports would not be reached).
    monkeypatch.setattr(install_mod, "apply", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code != 0, result.output
    assert "adopt failed" in result.output.lower()

    claude = project / "CLAUDE.md"
    assert claude.is_file() and not claude.is_symlink()
    assert claude.read_text() == "# mine\n"
    assert not (project / "CLAUDE.md.pre-adopt.bak").exists()
    assert (project / "AGENTS.md").read_text() == "# real canon\n"
    lock_file = project / "instructions-lock.json"
    if lock_file.exists():
        lock = json.loads(lock_file.read_text())
        assert lock.get("instructions", {}) == {}, "lock claims a fix that was rolled back"


def test_doctor_backup_fix_rolls_back_partial_apply_with_prior_lock(tmp_path, monkeypatch):
    """apply() that lays our slot's symlink then raises on a different slot must
    restore the user's file AND the prior lock verbatim — no half-applied state."""
    import agent_toolkit_cli.instructions_install as install_mod

    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# mine\n")
    (project / "instructions-lock.json").write_text(json.dumps({
        "version": 1,
        "instructions": {"AGENTS.md": {
            "scope": "project", "source": "AGENTS.md", "harnesses": ["gemini-cli"],
        }},
    }))
    monkeypatch.chdir(project)

    def apply_then_fail(*a, **k):
        # Simulate apply() creating our symlink (slot is free: the real file
        # was renamed to .bak), then failing on another slot.
        (project / "CLAUDE.md").symlink_to(project / "AGENTS.md")
        raise install_mod.CanonicalMissingError("boom on other slot")

    monkeypatch.setattr(install_mod, "apply", apply_then_fail)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code != 0, result.output

    claude = project / "CLAUDE.md"
    assert claude.is_file() and not claude.is_symlink(), "symlink not cleaned up on rollback"
    assert claude.read_text() == "# mine\n"
    assert not (project / "CLAUDE.md.pre-adopt.bak").exists()
    assert (project / "AGENTS.md").read_text() == "# real canon\n"
    lock = json.loads((project / "instructions-lock.json").read_text())
    assert lock["instructions"]["AGENTS.md"]["harnesses"] == ["gemini-cli"]


def test_doctor_backup_fix_rolls_back_when_lock_write_fails(tmp_path, monkeypatch):
    """write_lock failing right after the rename must restore the user's file
    from the .bak — otherwise the file is stranded at the .bak with an empty
    slot and a doctor re-run reports clean (critical-review finding, #375)."""
    import importlib

    # The instructions package re-exports the Click command `doctor_cmd` over
    # the submodule name, so attribute access yields a Command, not the
    # module — fetch the module explicitly to patch its namespace.
    doctor_mod = importlib.import_module(
        "agent_toolkit_cli.commands.instructions.doctor_cmd"
    )

    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# mine\n")
    monkeypatch.chdir(project)

    def boom(*a, **k):
        raise OSError("lock dir read-only")

    # doctor_cmd does `from ...instructions_lock import write_lock` — patch
    # the name in doctor_cmd's namespace. (No prior lock file exists, so the
    # rollback's lock-restore path takes the unlink branch and never calls
    # the patched write_lock itself.)
    monkeypatch.setattr(doctor_mod, "write_lock", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code != 0, result.output
    assert "adopt failed" in result.output.lower()

    claude = project / "CLAUDE.md"
    assert claude.is_file() and not claude.is_symlink()
    assert claude.read_text() == "# mine\n"
    assert not (project / "CLAUDE.md.pre-adopt.bak").exists()
    assert (project / "AGENTS.md").read_text() == "# real canon\n"
    assert not (project / "instructions-lock.json").exists()
