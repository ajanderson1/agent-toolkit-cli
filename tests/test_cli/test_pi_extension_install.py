"""Task 2: pi_extension_install facade — store-owned projection (plan + apply).

Tests: plan idempotency, apply creates symlink, foreign-dir/symlink guard.
Round-trip and CLI-level guards are in test_cli_pi_extension_write.py (Tasks 4-6).
"""
from pathlib import Path

import pytest

from agent_toolkit_cli import pi_extension_install as pei
from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.pi_extension_lock import LockEntry, LockFile, read_lock, write_lock


def _store_owned(tmp_path: Path, slug: str) -> Path:
    """Create a fake store-owned canonical dir + global lock entry."""
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


def test_plan_install_global_adds(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _store_owned(tmp_path, "ext")
    p = pei.plan(slug="ext", scope="global", action="install", home=tmp_path)
    assert p.create is True
    assert p.remove is False
    assert p.link == pep.pi_extension_dir("ext", scope="global", home=tmp_path)


def test_plan_install_already_linked_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _store_owned(tmp_path, "ext")
    link = pep.pi_extension_dir("ext", scope="global", home=tmp_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(canonical)
    p = pei.plan(slug="ext", scope="global", action="install", home=tmp_path)
    assert p.create is False and p.remove is False  # idempotent


def test_apply_install_creates_symlink_and_writes_lock_last(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _store_owned(tmp_path, "ext")
    p = pei.plan(slug="ext", scope="global", action="install", home=tmp_path)
    pei.apply(p, home=tmp_path)
    link = pep.pi_extension_dir("ext", scope="global", home=tmp_path)
    assert link.is_symlink()
    assert link.resolve() == canonical.resolve()


def test_apply_install_refuses_foreign_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _store_owned(tmp_path, "ext")
    link = pep.pi_extension_dir("ext", scope="global", home=tmp_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.mkdir()  # user-authored real dir squatting the slug
    (link / "index.ts").write_text("user's own ext")
    p = pei.plan(slug="ext", scope="global", action="install", home=tmp_path)
    with pytest.raises(pei.InstallError):
        pei.apply(p, home=tmp_path)
    # The user's dir is left intact.
    assert (link / "index.ts").read_text() == "user's own ext"


def test_apply_install_refuses_foreign_symlink(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _store_owned(tmp_path, "ext")
    other = tmp_path / "somewhere-else"
    other.mkdir()
    link = pep.pi_extension_dir("ext", scope="global", home=tmp_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(other)  # symlink, but not OURS
    p = pei.plan(slug="ext", scope="global", action="install", home=tmp_path)
    with pytest.raises(pei.InstallError):
        pei.apply(p, home=tmp_path)
    assert link.resolve() == other.resolve()  # untouched
