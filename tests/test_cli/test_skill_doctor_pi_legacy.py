"""Ownership and idempotence coverage for retiring Pi skill projections."""
from pathlib import Path
import json

import pytest

from agent_toolkit_cli.skill_doctor import diagnose
from agent_toolkit_cli.skill_paths import canonical_skill_dir


@pytest.fixture(params=["global", "project"])
def legacy_pi(request, tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(home / ".agent-toolkit/skills"))
    scope = request.param
    root = home / ".pi/agent/skills" if scope == "global" else project / ".pi/skills"
    root.mkdir(parents=True)
    canonical = canonical_skill_dir("demo", scope=scope, home=home, project=project)
    canonical.mkdir(parents=True)
    return scope, home, project, root, canonical


def _diagnose(state, *, slugs=None):
    scope, home, project, _, _ = state
    return diagnose(slugs=slugs, scope=scope, home=home, project=project)


def test_legacy_pi_preserves_foreign_symlinks(legacy_pi, tmp_path):
    _, _, _, root, _ = legacy_pi
    foreign = tmp_path / "user-skill"
    foreign.mkdir()
    link = root / "demo"
    link.symlink_to(foreign)
    assert not [f for f in _diagnose(legacy_pi) if f.path == link]
    assert link.resolve() == foreign


def test_legacy_pi_targeted_scan_and_idempotent_fix(legacy_pi):
    _, _, _, root, canonical = legacy_pi
    link = root / "demo"
    link.symlink_to(canonical)
    findings = [f for f in _diagnose(legacy_pi, slugs=("demo",)) if f.path == link]
    assert len(findings) == 1
    assert findings[0].fix_action is not None
    findings[0].fix_action.apply()
    findings[0].fix_action.apply()
    assert not link.is_symlink()
    assert canonical.is_dir()
    assert not [f for f in _diagnose(legacy_pi) if f.path == link]


def test_legacy_pi_fix_preserves_replaced_link(legacy_pi, tmp_path):
    _, _, _, root, canonical = legacy_pi
    link = root / "demo"
    link.symlink_to(canonical)
    finding = next(f for f in _diagnose(legacy_pi) if f.path == link)
    foreign = tmp_path / "user-skill"
    foreign.mkdir()
    link.unlink()
    link.symlink_to(foreign)
    finding.fix_action.apply()
    assert link.is_symlink()
    assert link.resolve() == foreign


def test_legacy_pi_fix_preserves_replacement_symlink_loop(legacy_pi):
    _, _, _, root, canonical = legacy_pi
    link = root / "demo"
    link.symlink_to(canonical)
    finding = next(f for f in _diagnose(legacy_pi) if f.path == link)
    link.unlink()
    link.symlink_to(link)

    finding.fix_action.apply()

    assert link.is_symlink()


def test_legacy_pi_fix_preserves_replaced_root(legacy_pi, tmp_path):
    _, _, _, root, canonical = legacy_pi
    link = root / "demo"
    link.symlink_to(canonical)
    finding = next(f for f in _diagnose(legacy_pi) if f.path == link)
    link.unlink()
    root.rmdir()
    external = tmp_path / "external-replacement"
    external.mkdir()
    root.symlink_to(external, target_is_directory=True)
    link.symlink_to(canonical)

    finding.fix_action.apply()

    assert link.is_symlink()


def test_legacy_pi_preserves_symlinked_root(legacy_pi, tmp_path):
    _, _, _, root, canonical = legacy_pi
    root.rmdir()
    external = tmp_path / "external-skills"
    external.mkdir()
    root.symlink_to(external, target_is_directory=True)
    link = external / "demo"
    link.symlink_to(canonical)
    assert not [f for f in _diagnose(legacy_pi) if f.path == root / "demo"]
    assert link.is_symlink()


def test_legacy_pi_global_external_registry_wins(legacy_pi):
    scope, home, _, root, canonical = legacy_pi
    if scope != "global":
        pytest.skip("external projection registry is global")
    link = root / "demo"
    link.symlink_to(canonical)
    registry = home / ".agent-toolkit/external-skill-projections.json"
    registry.write_text(json.dumps({
        "version": 1,
        "projections": [{
            "path": ".pi/agent/skills/demo",
            "targetGlob": ".agent-toolkit/skills/demo",
            "owner": "another-tool",
        }],
    }))
    assert not [f for f in _diagnose(legacy_pi) if f.path == link]
    assert link.is_symlink()


@pytest.mark.parametrize("register_after_diagnosis", [False, True])
def test_legacy_pi_preserves_registered_dangling_projection(
    legacy_pi, register_after_diagnosis
):
    scope, home, _, root, canonical = legacy_pi
    if scope != "global":
        pytest.skip("external projection registry is global-only")
    link = root / "demo"
    link.symlink_to(canonical)
    finding = None
    if register_after_diagnosis:
        finding = next(f for f in _diagnose(legacy_pi) if f.path == link)
    registry = home / ".agent-toolkit/external-skill-projections.json"
    registry.write_text(json.dumps({
        "version": 1,
        "projections": [{
            "path": ".pi/agent/skills/demo",
            "targetGlob": ".agent-toolkit/skills/demo",
            "owner": "another-tool",
        }],
    }))
    canonical.rmdir()

    if finding:
        finding.fix_action.apply()
    else:
        assert not [f for f in _diagnose(legacy_pi) if f.path == link]
    assert link.is_symlink()


def test_legacy_pi_fix_revalidates_canonical_target(legacy_pi, tmp_path):
    _, _, _, root, canonical = legacy_pi
    old_target = tmp_path / "old-canonical"
    new_target = tmp_path / "new-canonical"
    old_target.mkdir()
    new_target.mkdir()
    canonical.rmdir()
    canonical.symlink_to(old_target, target_is_directory=True)
    link = root / "demo"
    link.symlink_to(old_target)
    finding = next(f for f in _diagnose(legacy_pi) if f.path == link)
    canonical.unlink()
    canonical.symlink_to(new_target, target_is_directory=True)

    finding.fix_action.apply()

    assert link.is_symlink()
    assert link.resolve() == old_target


def test_legacy_pi_cli_reports_unlink_failure(legacy_pi, monkeypatch):
    from click.testing import CliRunner

    from agent_toolkit_cli.cli import main

    scope, _, project, root, canonical = legacy_pi
    link = root / "demo"
    link.symlink_to(canonical)
    original_unlink = Path.unlink

    def deny_legacy_unlink(path, *args, **kwargs):
        if path == link:
            raise PermissionError("legacy directory is read-only")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", deny_legacy_unlink)
    result = CliRunner().invoke(main, [
        "--project", str(project), "skill", "doctor", "demo",
        "-g" if scope == "global" else "-p",
    ], input="y\n")

    assert result.exit_code == 1, result.output
    assert "fix failed: legacy directory is read-only" in result.output
    assert "0 fixed, 1 skipped" in result.output
    assert link.is_symlink()


def test_legacy_pi_broken_owned_link_is_fixable(legacy_pi):
    _, _, _, root, canonical = legacy_pi
    canonical.rmdir()
    link = root / "demo"
    link.symlink_to(canonical)
    finding = next(f for f in _diagnose(legacy_pi) if f.path == link)
    finding.fix_action.apply()
    assert not link.is_symlink()
