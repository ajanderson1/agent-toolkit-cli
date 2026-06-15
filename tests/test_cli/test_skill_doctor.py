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
        finding_type="drifted_symlink", slug="demo", scope="global",
        path=Path("/tmp/x"), detail="example", fix_action=fa,
    )
    assert f.finding_type == "drifted_symlink"
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
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    _patch_claude_global_skills_dir(monkeypatch, fake_home / ".claude" / "skills")
    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global",
        home=fake_home, project=None,
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
    finding_types = [f.finding_type for f in findings]
    assert "missing_canonical" in finding_types


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
    f = next(f for f in findings if f.finding_type == "missing_canonical")
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
    drift = [f for f in findings if f.finding_type == "drifted_symlink"]
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
        if f.finding_type == "drifted_symlink"
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
    wrong = [f for f in findings if f.finding_type == "wrong_type_bundle"]
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
        if f.finding_type == "wrong_type_bundle"
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
    orphans = [f for f in findings if f.finding_type == "orphan_symlink"]
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
        if f.finding_type == "orphan_symlink"
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
    foreign_findings = [f for f in findings if f.finding_type == "foreign_symlink"]
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
    f = next(f for f in findings if f.finding_type == "foreign_symlink")
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
    dirty = [f for f in findings if f.finding_type == "dirty_tree"]
    assert len(dirty) == 1
    # Report-only.
    assert dirty[0].fix_action is None


def test_diagnose_v21_bundle_target_is_drift(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """A claude-code symlink that points at ~/.agents/skills/<slug>
    (the v2.1 bundle layout) must classify as drifted_symlink, not
    foreign_symlink — the user can apply the fix to relink to the library.
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

    # Plant the v2.1 layout: a real dir at ~/.agents/skills/demo and a
    # claude-code symlink pointing at it.
    bundle = fake_home / ".agents" / "skills" / "demo"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text("v2.1 leftover\n")
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    link = claude_skills / "demo"
    link.symlink_to(bundle)

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    drift = [f for f in findings if f.finding_type == "drifted_symlink" and f.path == link]
    foreign = [f for f in findings if f.finding_type == "foreign_symlink" and f.path == link]
    assert len(drift) == 1, [f.finding_type for f in findings]
    assert len(foreign) == 0
    # Fix action present and idempotent: relinks at library canonical.
    assert drift[0].fix_action is not None
    drift[0].fix_action.apply()
    assert link.is_symlink()
    assert link.resolve() == (library_root / "demo").resolve()
    drift[0].fix_action.apply()  # idempotent
    assert link.resolve() == (library_root / "demo").resolve()


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
    mismatch = [f for f in findings if f.finding_type == "lock_source_mismatch"]
    assert len(mismatch) == 1
    assert mismatch[0].fix_action is None


def test_normalise_git_url_ssh_https_equivalent():
    from agent_toolkit_cli.skill_doctor import _normalise_git_url
    ssh = "git@github.com:foo/bar.git"
    https = "https://github.com/foo/bar.git"
    https_no_suffix = "https://github.com/foo/bar"
    ssh_no_suffix = "git@github.com:foo/bar"
    assert _normalise_git_url(ssh) == _normalise_git_url(https)
    assert _normalise_git_url(https) == _normalise_git_url(https_no_suffix)
    assert _normalise_git_url(ssh) == _normalise_git_url(ssh_no_suffix)


def test_normalise_git_url_different_repos_differ():
    from agent_toolkit_cli.skill_doctor import _normalise_git_url
    assert (
        _normalise_git_url("https://github.com/foo/bar.git")
        != _normalise_git_url("https://github.com/foo/baz.git")
    )
    # Different hosts still differ.
    assert (
        _normalise_git_url("git@github.com:foo/bar.git")
        != _normalise_git_url("git@gitlab.com:foo/bar.git")
    )


def test_normalise_git_url_fallback_for_unknown_form():
    from agent_toolkit_cli.skill_doctor import _normalise_git_url
    # Local path - no regex matches, fallback strips trailing .git.
    assert _normalise_git_url("/tmp/some-remote.git") == "/tmp/some-remote"
    # Already-normalised string round-trips.
    assert _normalise_git_url("github.com/foo/bar") == "github.com/foo/bar"


def test_normalise_git_url_trailing_slash_variants():
    from agent_toolkit_cli.skill_doctor import _normalise_git_url
    canonical = _normalise_git_url("https://github.com/foo/bar.git")
    # HTTPS with trailing slash.
    assert _normalise_git_url("https://github.com/foo/bar/") == canonical
    # SSH `git@host:` form with trailing slash on `.git`.
    assert _normalise_git_url("git@github.com:foo/bar.git/") == canonical
    # Fallback path (no regex match) with trailing slash.
    assert _normalise_git_url("/tmp/some-remote.git/") == "/tmp/some-remote"


def test_diagnose_stray_symlink_global(git_sandbox, tmp_path: Path, monkeypatch):
    """A symlink in a projection dir whose basename isn't in the lock is stray."""
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
    _seed_library(runner, git_sandbox.upstream)  # adds 'demo' to lock

    # Plant a symlink for a slug that isn't in the lock at all.
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True, exist_ok=True)
    legacy_target = tmp_path / "legacy-skill"
    legacy_target.mkdir()
    stray = claude_skills / "old-slug"
    stray.symlink_to(legacy_target)

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    strays = [f for f in findings if f.finding_type == "stray_symlink"]
    assert len(strays) == 1
    assert strays[0].slug == "old-slug"
    assert strays[0].path == stray
    assert strays[0].fix_action is not None


def test_stray_symlink_fix_unlinks(git_sandbox, tmp_path: Path, monkeypatch):
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
    claude_skills.mkdir(parents=True, exist_ok=True)
    legacy_target = tmp_path / "legacy-skill"
    legacy_target.mkdir()
    stray = claude_skills / "old-slug"
    stray.symlink_to(legacy_target)

    from agent_toolkit_cli.skill_doctor import diagnose
    f = next(
        f for f in diagnose(
            slugs=None, scope="global", home=fake_home, project=None,
        )
        if f.finding_type == "stray_symlink"
    )
    f.fix_action.apply()
    assert not stray.is_symlink()
    # Idempotent.
    f.fix_action.apply()
    assert not stray.exists()


def test_stray_scan_skipped_when_slugs_provided(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """Doctor with explicit slugs only scans those slugs, not stray links."""
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
    claude_skills.mkdir(parents=True, exist_ok=True)
    legacy_target = tmp_path / "legacy-skill"
    legacy_target.mkdir()
    (claude_skills / "old-slug").symlink_to(legacy_target)

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=("demo",), scope="global", home=fake_home, project=None,
    )
    assert not any(f.finding_type == "stray_symlink" for f in findings)


def test_diagnose_stray_symlink_project(git_sandbox, tmp_path: Path, monkeypatch):
    """Project-scope stray scan finds legacy .claude/skills/* not in project lock."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    project = tmp_path / "proj"
    project.mkdir()
    # No project lock; plant a stray symlink in the project-scope claude dir.
    claude_skills = project / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    legacy_target = tmp_path / "legacy-skill"
    legacy_target.mkdir()
    stray = claude_skills / "aj-workflow"
    stray.symlink_to(legacy_target)

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="project", home=None, project=project,
    )
    strays = [f for f in findings if f.finding_type == "stray_symlink"]
    assert any(f.slug == "aj-workflow" and f.path == stray for f in strays)


def test_normalise_git_url_ssh_scheme_form():
    from agent_toolkit_cli.skill_doctor import _normalise_git_url
    canonical = _normalise_git_url("https://github.com/foo/bar.git")
    # `ssh://git@host/path` form (less common but valid).
    assert _normalise_git_url("ssh://git@github.com/foo/bar") == canonical
    assert _normalise_git_url("ssh://git@github.com/foo/bar.git") == canonical
    # Without explicit user.
    assert _normalise_git_url("ssh://github.com/foo/bar") == canonical


# ── #231: stray real-dir scan in ~/.agents/skills ────────────────────────


def _bundle_home(tmp_path: Path, monkeypatch) -> Path:
    """Fake HOME with an empty global lock, ready for ~/.agents/skills planting."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    _patch_claude_global_skills_dir(monkeypatch, fake_home / ".claude" / "skills")
    return fake_home


def test_diagnose_stray_bundle_dir_global(tmp_path: Path, monkeypatch):
    """A real dir in ~/.agents/skills/<slug> not in the lock → stray_bundle_dir."""
    fake_home = _bundle_home(tmp_path, monkeypatch)
    ghost = fake_home / ".agents" / "skills" / "ghost"
    (ghost / "sub").mkdir(parents=True)
    (ghost / "SKILL.md").write_text("# ghost\n")
    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(slugs=None, scope="global", home=fake_home, project=None)
    strays = [f for f in findings if f.finding_type == "stray_bundle_dir"]
    assert len(strays) == 1, [f.finding_type for f in findings]
    assert strays[0].slug == "ghost"
    assert strays[0].path == ghost
    assert strays[0].fix_action is not None


def test_stray_bundle_dir_fix_moves_to_bak(tmp_path: Path, monkeypatch):
    """The stray_bundle_dir fix moves the dir to a .bak-doctor-* sibling, not delete."""
    fake_home = _bundle_home(tmp_path, monkeypatch)
    ghost = fake_home / ".agents" / "skills" / "ghost"
    ghost.mkdir(parents=True)
    (ghost / "SKILL.md").write_text("# ghost\n")
    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(slugs=None, scope="global", home=fake_home, project=None)
    stray = next(f for f in findings if f.finding_type == "stray_bundle_dir")
    stray.fix_action.apply()
    assert not ghost.exists(), "original stray dir must be moved away"
    baks = list((fake_home / ".agents" / "skills").glob("ghost.bak-doctor-*"))
    assert len(baks) == 1, "stray must be preserved as a .bak-doctor-* backup"
    assert baks[0].is_dir() and not baks[0].is_symlink()
    assert (baks[0] / "SKILL.md").exists(), "backup must preserve contents"


def test_stray_bundle_dir_skips_symlink(tmp_path: Path, monkeypatch):
    """A symlink in ~/.agents/skills (correct v2.2 install) is never flagged stray."""
    fake_home = _bundle_home(tmp_path, monkeypatch)
    target = tmp_path / "real-skill"
    target.mkdir()
    bundle_root = fake_home / ".agents" / "skills"
    bundle_root.mkdir(parents=True)
    (bundle_root / "linked").symlink_to(target)
    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(slugs=None, scope="global", home=fake_home, project=None)
    assert not [f for f in findings if f.finding_type == "stray_bundle_dir"]


def test_diagnose_bak_doctor_dirs_offered_for_cleanup(tmp_path: Path, monkeypatch):
    """A leftover *.bak-doctor-* dir in the bundle root is offered for removal."""
    fake_home = _bundle_home(tmp_path, monkeypatch)
    bak = fake_home / ".agents" / "skills" / "ghost.bak-doctor-20250101-120000"
    bak.mkdir(parents=True)
    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(slugs=None, scope="global", home=fake_home, project=None)
    bak_findings = [f for f in findings if f.path == bak]
    assert len(bak_findings) == 1, [f.finding_type for f in findings]
    bak_findings[0].fix_action.apply()
    assert not bak.exists(), "leftover backup must be removable by the fix"


def test_stray_bundle_dir_skips_known_slug(git_sandbox, tmp_path: Path, monkeypatch):
    """A real dir whose slug IS in the lock is not double-reported as stray.

    (That case is wrong_type_bundle's job, handled by _check_slug.)
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
    _seed_library(runner, git_sandbox.upstream)  # 'demo' now in the global lock

    # Plant a real dir at ~/.agents/skills/demo (slug IS in the lock).
    demo_bundle = fake_home / ".agents" / "skills" / "demo"
    demo_bundle.mkdir(parents=True)
    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(slugs=None, scope="global", home=fake_home, project=None)
    assert not [f for f in findings if f.finding_type == "stray_bundle_dir"], \
        "in-lock real dir must not be reported as stray_bundle_dir"


# ── #360 AC4: unlisted finding ────────────────────────────────────────────


def test_unlisted_finding_fires_at_project_scope(git_sandbox, tmp_path, monkeypatch):
    """#360 AC4: project lock entry whose slug is missing from the library lock."""
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    (project / ".claude").mkdir(exist_ok=True)
    r = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, ["skill", "remove", "demo", "--force"])
    assert r.exit_code == 0, r.output

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(slugs=None, scope="project", home=None, project=project)
    unlisted = [f for f in findings if f.finding_type == "unlisted"]
    assert len(unlisted) == 1
    assert unlisted[0].slug == "demo"
    assert unlisted[0].fix_action is not None


def test_unlisted_fix_action_readds_to_library(git_sandbox, tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    (project / ".claude").mkdir(exist_ok=True)
    r = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, ["skill", "remove", "demo", "--force"])
    assert r.exit_code == 0, r.output

    from agent_toolkit_cli.skill_doctor import diagnose
    from agent_toolkit_cli.skill_lock import read_lock
    from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path

    findings = diagnose(slugs=None, scope="project", home=None, project=project)
    fix = next(f for f in findings if f.finding_type == "unlisted").fix_action
    fix.apply()
    fix.apply()  # idempotent: second apply is a no-op, not an error

    assert "demo" in read_lock(library_lock_path()).skills   # lock entry restored
    assert library_skill_path("demo").exists()               # canonical re-materialised
    # Finding clears on the next run.
    findings2 = diagnose(slugs=None, scope="project", home=None, project=project)
    assert not [f for f in findings2 if f.finding_type == "unlisted"]


def test_unlisted_not_checked_at_global_scope(tmp_path, monkeypatch):
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    assert not [f for f in findings if f.finding_type == "unlisted"]


def test_unlisted_not_fired_for_targeted_doctor(git_sandbox, tmp_path, monkeypatch):
    """Targeted skill doctor <slug> -p does NOT fire the unlisted finding (sweep-only)."""
    project = tmp_path / "proj"
    project.mkdir()
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    (project / ".claude").mkdir(exist_ok=True)
    r = runner.invoke(main, [
        "--project", str(project),
        "skill", "install", "demo", "--scope", "project",
        "--agents", "claude-code",
    ])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, ["skill", "remove", "demo", "--force"])
    assert r.exit_code == 0, r.output

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(slugs=("demo",), scope="project", home=None, project=project)
    assert not [f for f in findings if f.finding_type == "unlisted"]


# --- #412: doctor reuses legacy bare-named parent clone ---

def test_doctor_reclone_reuses_legacy_bare_parent(tmp_path, monkeypatch):
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref, _lock, _make_legacy_bare,
    )
    from agent_toolkit_cli import skill_doctor
    from agent_toolkit_cli.skill_paths import (
        canonical_skill_dir, parent_clone_path,
    )

    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    bare = _make_legacy_bare(entry)

    # Break the canonical so the reclone fix-action fires.
    canonical = canonical_skill_dir(
        "mkdocs", scope="global", home=None, project=None,
    )
    if canonical.is_symlink() or canonical.exists():
        canonical.unlink()

    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    fix = next(f.fix_action for f in findings if f.fix_action)
    fix.apply()

    # It re-linked against the EXISTING bare clone, not a new suffixed clone.
    owner, repo = entry["source"].split("/", 1)
    suffixed = parent_clone_path(owner, repo, ref=entry["ref"], env=None)
    assert bare.exists()
    assert not suffixed.exists()  # no divergent re-clone
    assert canonical.exists()


# --- #412 Phase 2: doctor legacy_bare_parent finding + alias fix ---

def test_doctor_flags_legacy_bare_parent(tmp_path, monkeypatch):
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref, _lock, _make_legacy_bare,
    )
    from agent_toolkit_cli import skill_doctor
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    _make_legacy_bare(entry)
    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    legacy = [f for f in findings if f.finding_type == "legacy_bare_parent"]
    assert legacy, [f.finding_type for f in findings]


def test_doctor_flags_legacy_bare_when_suffixed_exists_but_not_repo(tmp_path, monkeypatch):
    """#422 fix 2 — doctor must surface the legacy_bare_parent finding when the
    suffixed path EXISTS but is NOT a git repo (a partial/aborted clone) beside
    an adoptable bare clone. The resolver already adopts the bare in this case
    (its gate is `is_git_repo(suffixed)`), so doctor must fire on the same
    condition (`not is_git_repo(suffixed)`), not the narrower `not exists()`."""
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref, _lock, _make_legacy_bare,
    )
    from agent_toolkit_cli import skill_doctor
    from agent_toolkit_cli.skill_paths import parent_clone_path
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    _make_legacy_bare(entry)  # renames suffixed -> bare (suffixed now absent)
    owner, repo = entry["source"].split("/", 1)
    suffixed = parent_clone_path(owner, repo, ref=entry["ref"], env=None)
    # Recreate the suffixed path as a partial clone: exists, but NOT a git repo.
    suffixed.mkdir(parents=True)
    (suffixed / "stray").write_text("partial")
    assert not (suffixed / ".git").exists()
    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    legacy = [f for f in findings if f.finding_type == "legacy_bare_parent"]
    assert legacy, [f.finding_type for f in findings]


def test_doctor_legacy_bare_fix_converges_on_partial_suffixed_clone(tmp_path, monkeypatch):
    """#422 fix 2 — the alias fix must CONVERGE when suffixed exists as a partial
    (non-repo) clone: apply moves the partial dir aside and creates the alias, so
    a re-diagnose clears the finding (the early-return idempotency guard alone
    would no-op and loop forever)."""
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref, _lock, _make_legacy_bare,
    )
    from agent_toolkit_cli import skill_doctor
    from agent_toolkit_cli.skill_paths import parent_clone_path
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    bare = _make_legacy_bare(entry)
    owner, repo = entry["source"].split("/", 1)
    suffixed = parent_clone_path(owner, repo, ref=entry["ref"], env=None)
    suffixed.mkdir(parents=True)
    (suffixed / "stray").write_text("partial")

    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    fix = next(
        f.fix_action for f in findings
        if f.finding_type == "legacy_bare_parent" and f.fix_action
    )
    fix.apply()
    # The partial dir was moved aside and the alias now points at the bare clone.
    assert suffixed.is_symlink()
    assert suffixed.resolve() == bare.resolve()
    assert suffixed.with_name(suffixed.name + ".attk-partial").exists()
    # Re-diagnose: finding has converged (gone).
    again = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    assert not [f for f in again if f.finding_type == "legacy_bare_parent"]


def test_doctor_legacy_bare_fix_creates_alias_symlink(tmp_path, monkeypatch):
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref, _lock, _make_legacy_bare,
    )
    from agent_toolkit_cli import skill_doctor
    from agent_toolkit_cli.skill_paths import parent_clone_path
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    bare = _make_legacy_bare(entry)
    owner, repo = entry["source"].split("/", 1)
    suffixed = parent_clone_path(owner, repo, ref=entry["ref"], env=None)

    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    fix = next(
        f.fix_action for f in findings
        if f.finding_type == "legacy_bare_parent" and f.fix_action
    )
    fix.apply()
    assert suffixed.is_symlink()
    assert suffixed.resolve() == bare.resolve()
    # idempotent: re-applying with the alias present is a no-op, no raise.
    fix.apply()


def test_doctor_no_legacy_finding_when_suffixed_present(tmp_path, monkeypatch):
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref,
    )
    from agent_toolkit_cli import skill_doctor
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")  # leaves the suffixed clone in place
    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    assert not [f for f in findings if f.finding_type == "legacy_bare_parent"]


def test_doctor_no_legacy_finding_when_remote_mismatch(tmp_path, monkeypatch):
    """A bare dir whose origin does NOT match parentUrl must not be flagged."""
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref, _lock, _make_legacy_bare,
    )
    from tests.conftest import scrub_git_env
    from agent_toolkit_cli import skill_doctor
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    bare = _make_legacy_bare(entry)
    subprocess.run(
        ["git", "-C", str(bare), "remote", "set-url", "origin",
         "https://github.com/someone/else"],
        check=True, env=scrub_git_env(),
    )
    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    assert not [f for f in findings if f.finding_type == "legacy_bare_parent"]


def test_doctor_no_legacy_finding_when_bare_on_different_ref(tmp_path, monkeypatch):
    """Multi-ref safety (#412): the bare clone is checked out on a DIFFERENT ref
    than the lock entry records (the shared-monorepo P1 scenario). Doctor must
    NOT offer to alias `<repo>@main -> <repo>` — that would misrepresent the bare
    clone (which is on `other`) and let a later update flip the shared tree.
    The read-path resolver and doctor share `legacy_bare_clone_for`, so this
    refusal is the doctor-side mirror of the resolver's off-ref rejection.
    """
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref, _lock, _make_legacy_bare,
    )
    from tests.conftest import scrub_git_env
    from agent_toolkit_cli import skill_doctor
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")  # lock records ref=main
    entry = _lock()["skills"]["mkdocs"]
    bare = _make_legacy_bare(entry)  # bare materialised on main, then…
    subprocess.run(  # …flipped to a different branch
        ["git", "-C", str(bare), "checkout", "-q", "-b", "other"],
        check=True, env=scrub_git_env(),
    )
    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    assert not [f for f in findings if f.finding_type == "legacy_bare_parent"]
