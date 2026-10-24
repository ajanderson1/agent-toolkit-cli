import pytest
from agent_toolkit_cli import pi_extension_install
"""Task 2 (#333): pi_extension_ops install/uninstall core (global scope).

The core is the single path the CLI and TUI both call. These tests lock the
two behaviours the bug got wrong: npm global uninstall must remove drifted
packages[] entries, and store-owned global uninstall must drop the symlink
but KEEP the global library lock entry (uninstall != remove)."""
import json

from agent_toolkit_cli import pi_extension_ops as ops
from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.pi_extension_lock import (
    LockEntry, LockFile, read_lock, write_lock,
)


def _global_settings(home):
    return home / ".pi" / "agent" / "settings.json"


def _seed_settings(home, obj):
    p = _global_settings(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2) + "\n")


def _seed_npm_lock(slug, source):
    lock_path = pep.library_lock_path(env={})
    lf = read_lock(lock_path)
    lf = LockFile(version=lf.version, skills={
        **lf.skills, slug: LockEntry(source=source, source_type="npm"),
    })
    write_lock(lock_path, lf)


def _seed_store_owned(home, slug):
    canonical = pep.library_pi_extension_path(slug, env={})
    canonical.mkdir(parents=True)
    (canonical / "index.ts").write_text("export default {}")
    lock_path = pep.library_lock_path(env={})
    lf = read_lock(lock_path)
    lf = LockFile(version=lf.version, skills={
        **lf.skills,
        slug: LockEntry(source="github.com/o/" + slug, source_type="github",
                        pi_extension_path=slug),
    })
    write_lock(lock_path, lf)
    return canonical


def test_uninstall_store_owned_global_drops_symlink_keeps_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_store_owned(tmp_path, "demo")
    # project it on first.
    ops.install(slug="demo", scope="global", home=tmp_path, project=None)
    link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    assert link.is_symlink()
    # now uninstall.
    ops.uninstall(slug="demo", scope="global", home=tmp_path, project=None)
    assert not link.exists()                       # symlink gone
    assert canonical.exists()                      # library copy retained
    lock = read_lock(pep.library_lock_path(env={}))
    assert "demo" in lock.skills                   # lock entry retained (not remove)


def test_project_install_store_owned_fails_when_global_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_store_owned(tmp_path, "demo")

    ops.install(slug="demo", scope="global", home=tmp_path, project=None)
    project = tmp_path / "proj"
    project.mkdir()

    with pytest.raises(ops.pi_extension_install.InstallError) as exc:
        ops.install(slug="demo", scope="project", home=tmp_path, project=project)

    assert "already installed at global scope" in str(exc.value)
    project_link = pep.pi_extension_dir("demo", scope="project", project=project)
    assert not project_link.exists()
    assert canonical.exists()


def test_project_install_succeeds_after_global_uninstall(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_store_owned(tmp_path, "demo")
    project = tmp_path / "proj"
    project.mkdir()

    ops.install(slug="demo", scope="global", home=tmp_path, project=None)
    ops.uninstall(slug="demo", scope="global", home=tmp_path, project=None)
    ops.install(slug="demo", scope="project", home=tmp_path, project=project)

    project_link = pep.pi_extension_dir("demo", scope="project", project=project)
    assert project_link.is_symlink()


def test_project_uninstall_still_allowed_when_global_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_store_owned(tmp_path, "demo")
    project = tmp_path / "proj"
    project.mkdir()

    global_link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    global_link.parent.mkdir(parents=True, exist_ok=True)
    global_link.symlink_to(canonical, target_is_directory=True)
    project_link = pep.pi_extension_dir("demo", scope="project", project=project)
    project_link.parent.mkdir(parents=True, exist_ok=True)
    project_link.symlink_to(canonical, target_is_directory=True)

    ops.uninstall(slug="demo", scope="project", home=tmp_path, project=project)

    assert global_link.is_symlink()
    assert not project_link.exists()
