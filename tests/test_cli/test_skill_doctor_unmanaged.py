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


def test_doctor_repair_never_imports_local_skill(tmp_path: Path, monkeypatch):
    fake_home, lib_root = _setup_env(monkeypatch, tmp_path)
    unmanaged = lib_root / "custom-skill"
    unmanaged.mkdir(parents=True)
    content = "---\nname: custom-skill\ndescription: test\n---\n"
    (unmanaged / "SKILL.md").write_text(content)

    result = CliRunner().invoke(main, ["skill", "doctor", "-g", "--repair"], input="y\n")
    assert result.exit_code != 0, result.output
    assert "custom-skill" in result.output
    assert "Apply?" not in result.output
    assert "Import unmanaged" not in result.output
    assert "custom-skill" not in read_lock(library_lock_path(home=fake_home)).skills
    assert (unmanaged / "SKILL.md").read_text() == content


def test_doctor_repair_never_imports_bundle_child(tmp_path: Path, monkeypatch):
    fake_home, lib_root = _setup_env(monkeypatch, tmp_path)
    child = lib_root / "superpowers" / "skills" / "brainstorming"
    child.mkdir(parents=True)
    (child / "SKILL.md").write_text("---\nname: brainstorming\n---\n")

    result = CliRunner().invoke(main, ["skill", "doctor", "-g", "--repair"], input="y\n")
    assert result.exit_code != 0, result.output
    assert "superpowers:brainstorming" in result.output
    assert not read_lock(library_lock_path(home=fake_home)).skills
    assert (child / "SKILL.md").exists()


def test_local_findings_have_no_repair_in_either_scope(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_doctor import diagnose
    from agent_toolkit_cli.skill_paths import project_store_root

    home, library = _setup_env(monkeypatch, tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    for scope, root in (("global", library), ("project", project_store_root(project))):
        child = root / "local-child"
        child.mkdir(parents=True)
        (child / "SKILL.md").write_text("local")
        findings = diagnose(slugs=("local-child",), scope=scope, home=home,
                            project=project if scope == "project" else None, repair=True)
        local = [f for f in findings if f.finding_type == "unmanaged"]
        assert len(local) == 1
        assert local[0].path == child
        assert local[0].fix_action is None
