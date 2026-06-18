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


def test_uninstall_npm_global_removes_drifted_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm_lock("foo", "npm:foo")
    # settings has a version-pinned, prefix-less drift variant.
    _seed_settings(tmp_path, {"packages": ["foo@1.2.3", "npm:keep"]})
    ops.uninstall(slug="foo", scope="global", home=tmp_path, project=None)
    body = json.loads(_global_settings(tmp_path).read_text())
    assert body["packages"] == ["npm:keep"]


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


def test_install_npm_global_adds_package(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_npm_lock("foo", "npm:foo")
    ops.install(slug="foo", scope="global", home=tmp_path, project=None)
    body = json.loads(_global_settings(tmp_path).read_text())
    assert body["packages"] == ["npm:foo"]

def test_uninstall_unmanaged_npm_raises_with_advice(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".pi" / "agent" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"packages": ["npm:pi-title-renamer"]}))

    with pytest.raises(pi_extension_install.InstallError) as excinfo:
        ops.uninstall(slug="pi-title-renamer", scope="global", home=tmp_path)

    message = str(excinfo.value)
    assert "unmanaged npm package" in message
    assert "will not remove packages it did not add" in message
    assert str(settings) in message
    assert 'remove "npm:pi-title-renamer" from packages[]' in message

def test_uninstall_unmanaged_npm_project_scope_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".pi" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"packages": ["npm:pi-title-renamer"]}))

    with pytest.raises(pi_extension_install.InstallError) as excinfo:
        ops.uninstall(slug="pi-title-renamer", scope="project", project=tmp_path)

    message = str(excinfo.value)
    assert "unmanaged npm package" in message
    assert "will not remove packages it did not add" in message
    assert str(settings) in message
    assert 'remove "npm:pi-title-renamer" from packages[]' in message
