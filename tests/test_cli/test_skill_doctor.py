"""Tests for skill_doctor diagnose + fix engine."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import replace as dc_replace
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli import skill_agents
from agent_toolkit_cli.cli import main
from agent_toolkit_cli.skill_doctor import FixAction, Finding


def test_finding_has_expected_fields():
    fa = FixAction(
        description="noop", shell_preview="true", apply=lambda: None,
    )
    f = Finding(
        kind="drifted_symlink", slug="demo", scope="global",
        path=Path("/tmp/x"), detail="example", fix_action=fa,
    )
    assert f.kind == "drifted_symlink"
    assert f.slug == "demo"
    assert f.scope == "global"
    assert f.path == Path("/tmp/x")
    assert f.detail == "example"
    assert f.fix_action is fa


def test_fix_action_apply_is_callable():
    calls: list[int] = []
    fa = FixAction(
        description="touch", shell_preview="touch x",
        apply=lambda: calls.append(1),
    )
    fa.apply()
    fa.apply()
    assert calls == [1, 1]


def test_diagnose_empty_lock_returns_no_findings(tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global",
        home=tmp_path / "home", project=None,
    )
    assert findings == []


def _seed_library(runner, upstream_path) -> None:
    """Add 'demo' to the global library lock."""
    r = runner.invoke(main, ["skill", "add", str(upstream_path), "--slug", "demo"])
    assert r.exit_code == 0, r.output


def test_diagnose_missing_canonical(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    # Delete the library canonical behind the lock's back.
    shutil.rmtree(library_root / "demo")

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    kinds = [f.kind for f in findings]
    assert "missing_canonical" in kinds


def test_missing_canonical_fix_reclones(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)
    shutil.rmtree(library_root / "demo")

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    f = next(f for f in findings if f.kind == "missing_canonical")
    assert f.fix_action is not None
    f.fix_action.apply()
    assert (library_root / "demo" / "SKILL.md").exists()
    # Idempotent: second apply is a no-op.
    f.fix_action.apply()
    assert (library_root / "demo" / "SKILL.md").exists()


def test_make_remove_entry_action_drops_lock_row(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    from agent_toolkit_cli.skill_doctor import make_remove_entry_action
    from agent_toolkit_cli.skill_lock import read_lock
    from agent_toolkit_cli.skill_paths import library_lock_path

    action = make_remove_entry_action(
        slug="demo", scope="global", home=fake_home, project=None,
    )
    action.apply()

    lock = read_lock(library_lock_path())
    assert "demo" not in lock.skills
    # Idempotent.
    action.apply()
    lock = read_lock(library_lock_path())
    assert "demo" not in lock.skills


def _patch_claude_global_skills_dir(monkeypatch, new_dir: Path) -> None:
    """Replace AGENTS['claude-code'] with a copy pointing global_skills_dir at new_dir.

    AgentConfig is frozen=True so we swap the dict entry rather than mutating the
    instance. monkeypatch restores the original entry on teardown.
    """
    original = skill_agents.AGENTS["claude-code"]
    monkeypatch.setitem(skill_agents.AGENTS, "claude-code", dc_replace(original, global_skills_dir=new_dir))


def _setup_drifted_symlink_sandbox(
    git_sandbox, tmp_path: Path, monkeypatch,
) -> tuple[Path, Path, Path]:
    """Seed a global library with 'demo' and plant a stale claude-code symlink.

    Returns (fake_home, library_root, stale_link).
    """
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    _patch_claude_global_skills_dir(monkeypatch, fake_home / ".claude" / "skills")

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    # Stale symlink → another path WITHIN library_root (so it's drift, not foreign).
    elsewhere = library_root / "elsewhere-slug"
    elsewhere.mkdir(parents=True)
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    stale = claude_skills / "demo"
    stale.symlink_to(elsewhere)

    return fake_home, library_root, stale


def test_diagnose_drifted_symlink_global(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home, _library_root, stale = _setup_drifted_symlink_sandbox(
        git_sandbox, tmp_path, monkeypatch,
    )

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    drift = [f for f in findings if f.kind == "drifted_symlink"]
    assert len(drift) == 1
    assert drift[0].path == stale


def test_drifted_symlink_fix_relinks(git_sandbox, tmp_path: Path, monkeypatch):
    fake_home, library_root, stale = _setup_drifted_symlink_sandbox(
        git_sandbox, tmp_path, monkeypatch,
    )

    from agent_toolkit_cli.skill_doctor import diagnose
    f = next(
        f for f in diagnose(
            slugs=None, scope="global", home=fake_home, project=None,
        )
        if f.kind == "drifted_symlink"
    )
    f.fix_action.apply()
    assert stale.is_symlink()
    assert stale.resolve() == (library_root / "demo").resolve()
    # Idempotent.
    f.fix_action.apply()
    assert stale.resolve() == (library_root / "demo").resolve()


def test_diagnose_wrong_type_bundle_global(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    # Create a REAL directory at the bundle path (the v2.1-era layout).
    bundle = fake_home / ".agents" / "skills" / "demo"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text("v2.1 leftover\n")

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    wrong = [f for f in findings if f.kind == "wrong_type_bundle"]
    assert len(wrong) == 1
    assert wrong[0].path == bundle


def test_wrong_type_bundle_fix_moves_and_relinks(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)
    bundle = fake_home / ".agents" / "skills" / "demo"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text("v2.1 leftover\n")

    from agent_toolkit_cli.skill_doctor import diagnose
    f = next(
        f for f in diagnose(
            slugs=None, scope="global", home=fake_home, project=None,
        )
        if f.kind == "wrong_type_bundle"
    )
    f.fix_action.apply()

    assert bundle.is_symlink()
    assert bundle.resolve() == (library_root / "demo").resolve()
    # Backup directory was created with a .bak-doctor- prefix.
    backups = list(bundle.parent.glob("demo.bak-doctor-*"))
    assert len(backups) == 1
    # Idempotent: applying again does nothing destructive.
    f.fix_action.apply()
    assert bundle.is_symlink()


def test_diagnose_orphan_symlink(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    _patch_claude_global_skills_dir(monkeypatch, fake_home / ".claude" / "skills")

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)
    # Symlink to a path that doesn't exist.
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    broken = claude_skills / "demo"
    broken.symlink_to(tmp_path / "does-not-exist")

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    orphans = [f for f in findings if f.kind == "orphan_symlink"]
    assert len(orphans) == 1


def test_orphan_symlink_fix_unlinks(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    _patch_claude_global_skills_dir(monkeypatch, fake_home / ".claude" / "skills")

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    broken = claude_skills / "demo"
    broken.symlink_to(tmp_path / "does-not-exist")

    from agent_toolkit_cli.skill_doctor import diagnose
    f = next(
        f for f in diagnose(
            slugs=None, scope="global", home=fake_home, project=None,
        )
        if f.kind == "orphan_symlink"
    )
    f.fix_action.apply()
    assert not broken.is_symlink()
    assert not broken.exists()
    # Idempotent.
    f.fix_action.apply()
    assert not broken.exists()


def test_diagnose_foreign_symlink_report_only(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    _patch_claude_global_skills_dir(monkeypatch, fake_home / ".claude" / "skills")

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    # Foreign target outside the library root — but the path EXISTS so it's
    # not orphan; and it's NOT inside library_root so it's foreign rather
    # than drifted.
    foreign = tmp_path / "user-handrolled-skill"
    foreign.mkdir()
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    link = claude_skills / "demo"
    link.symlink_to(foreign)

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    foreign_findings = [f for f in findings if f.kind == "foreign_symlink"]
    assert len(foreign_findings) == 1
    # Report-only by default.
    assert foreign_findings[0].fix_action is None


def test_diagnose_foreign_symlink_repair_foreign(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    _patch_claude_global_skills_dir(monkeypatch, fake_home / ".claude" / "skills")

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    foreign = tmp_path / "user-handrolled-skill"
    foreign.mkdir()
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    link = claude_skills / "demo"
    link.symlink_to(foreign)

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
        repair_foreign=True,
    )
    f = next(f for f in findings if f.kind == "foreign_symlink")
    assert f.fix_action is not None
    f.fix_action.apply()
    assert not link.is_symlink()


def test_diagnose_dirty_tree(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)
    # Dirty the canonical.
    (library_root / "demo" / "SKILL.md").write_text("edited\n")

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    dirty = [f for f in findings if f.kind == "dirty_tree"]
    assert len(dirty) == 1
    # Report-only.
    assert dirty[0].fix_action is None


def test_diagnose_lock_source_mismatch(git_sandbox, tmp_path: Path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    # Point origin at a different URL on disk.
    other = tmp_path / "other-remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(library_root / "demo"),
         "remote", "set-url", "origin", str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    mismatch = [f for f in findings if f.kind == "lock_source_mismatch"]
    assert len(mismatch) == 1
    assert mismatch[0].fix_action is None
