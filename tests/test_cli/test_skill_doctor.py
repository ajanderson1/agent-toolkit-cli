"""Tests for skill_doctor diagnose + fix engine."""
from __future__ import annotations

import shutil
from pathlib import Path

from click.testing import CliRunner

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
