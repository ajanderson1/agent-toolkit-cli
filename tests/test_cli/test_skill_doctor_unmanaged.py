"""Tests for skill doctor unmanaged asset discovery and safe confirmed repair."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import library_lock_path


def _setup_env(monkeypatch, tmp_path: Path):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    lib_root = fake_home / ".agent-toolkit" / "skills"
    lib_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(lib_root))
    return fake_home, lib_root


def test_doctor_discovers_unmanaged_skill_report_only_without_repair(tmp_path: Path, monkeypatch):
    """Doctor without --repair reports unmanaged skill but does not prompt or mutate."""
    fake_home, lib_root = _setup_env(monkeypatch, tmp_path)
    # Create unmanaged skill on disk
    unmanaged = lib_root / "custom-skill"
    unmanaged.mkdir(parents=True)
    (unmanaged / "SKILL.md").write_text("---\nname: custom-skill\ndescription: test\n---\n")

    runner = CliRunner()
    # No --repair flag: report only
    r = runner.invoke(main, ["skill", "doctor", "-g"])
    assert r.exit_code != 0
    assert "custom-skill" in r.output
    assert "unmanaged" in r.output
    # Must not have mutated lockfile
    lock = read_lock(library_lock_path(home=fake_home))
    assert "custom-skill" not in lock.skills
    assert (unmanaged / "SKILL.md").exists()


def test_doctor_no_fix_overrides_repair(tmp_path: Path, monkeypatch):
    """--no-fix keeps doctor in report-only mode even with --repair."""
    fake_home, lib_root = _setup_env(monkeypatch, tmp_path)
    unmanaged = lib_root / "custom-skill"
    unmanaged.mkdir(parents=True)
    (unmanaged / "SKILL.md").write_text("---\nname: custom-skill\ndescription: test\n---\n")

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "doctor", "-g", "--repair", "--no-fix"])
    assert r.exit_code != 0
    assert "custom-skill" in r.output
    lock = read_lock(library_lock_path(home=fake_home))
    assert "custom-skill" not in lock.skills


def test_doctor_repair_declined_leaves_lock_and_source_untouched(tmp_path: Path, monkeypatch):
    """When user declines repair confirmation, no change is made."""
    fake_home, lib_root = _setup_env(monkeypatch, tmp_path)
    unmanaged = lib_root / "custom-skill"
    unmanaged.mkdir(parents=True)
    (unmanaged / "SKILL.md").write_text("---\nname: custom-skill\ndescription: test\n---\n")

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "doctor", "-g", "--repair"], input="N\n")
    assert r.exit_code != 0
    assert "custom-skill" in r.output
    lock = read_lock(library_lock_path(home=fake_home))
    assert "custom-skill" not in lock.skills
    assert (unmanaged / "SKILL.md").exists()


def test_doctor_repair_confirmed_imports_skill_losslessly(tmp_path: Path, monkeypatch):
    """When user confirms repair, unmanaged skill is imported into lock."""
    fake_home, lib_root = _setup_env(monkeypatch, tmp_path)
    unmanaged = lib_root / "custom-skill"
    unmanaged.mkdir(parents=True)
    skill_content = "---\nname: custom-skill\ndescription: test content\n---\n"
    (unmanaged / "SKILL.md").write_text(skill_content)

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "doctor", "-g", "--repair"], input="y\n")
    assert r.exit_code == 0, r.output
    assert "fixed" in r.output

    # Verified in lock
    lock = read_lock(library_lock_path(home=fake_home))
    assert "custom-skill" in lock.skills
    entry = lock.skills["custom-skill"]
    assert entry.source_type == "local"
    # Source content completely preserved
    assert (unmanaged / "SKILL.md").read_text() == skill_content

    # Repeat run of doctor: now all clean!
    r2 = runner.invoke(main, ["skill", "doctor", "-g"])
    assert r2.exit_code == 0, r2.output
    assert "clean" in r2.output.lower()


def test_doctor_repair_bundle_subskill(tmp_path: Path, monkeypatch):
    """Bundle subskills (bundle:subskill) are imported with bundle layout preserved."""
    fake_home, lib_root = _setup_env(monkeypatch, tmp_path)
    bundle_sub = lib_root / "superpowers" / "skills" / "brainstorming"
    bundle_sub.mkdir(parents=True)
    (bundle_sub / "SKILL.md").write_text("---\nname: brainstorming\ndescription: think\n---\n")

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "doctor", "-g", "--repair"], input="y\n")
    assert r.exit_code == 0, r.output

    lock = read_lock(library_lock_path(home=fake_home))
    assert "superpowers:brainstorming" in lock.skills
    assert (bundle_sub / "SKILL.md").exists()
