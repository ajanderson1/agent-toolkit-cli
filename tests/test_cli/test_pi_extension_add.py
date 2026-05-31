"""`pi-extension add` core tests (Task 3).

Lock-after-clone, idempotency, npm record, store-owned clone.
"""
from pathlib import Path

import pytest

from agent_toolkit_cli import pi_extension_add as pea
from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.pi_extension_lock import read_lock


def test_add_npm_records_registry_entry_no_clone(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    pea.add(source="npm:@scope/rpiv-i18n", slug=None, env={})
    lock = read_lock(pep.library_lock_path(env={}))
    entry = lock.skills["@scope/rpiv-i18n"]
    assert entry.source == "npm:@scope/rpiv-i18n"
    assert entry.source_type == "npm"
    assert entry.pi_extension_path is None  # not stored
    # No store dir created.
    assert not pep.library_pi_extension_path("@scope/rpiv-i18n", env={}).exists()


def test_add_store_owned_clones_and_records(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    # git_sandbox.upstream is a bare repo seeded with SKILL.md; reuse as a
    # generic git source. Add as a store-owned extension named "demo".
    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)
    canonical = pep.library_pi_extension_path("demo", env={})
    assert canonical.exists()
    lock = read_lock(pep.library_lock_path(env={}))
    entry = lock.skills["demo"]
    assert entry.source_type != "npm"
    assert entry.pi_extension_path == "demo"


def test_add_lock_written_only_after_clone(tmp_path, monkeypatch):
    # A clone failure (bad source) must NOT leave a lock entry behind (#283).
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(Exception):  # noqa: BLE001
        pea.add(source="/nonexistent/does-not-exist-xyz", slug="ghost", env={})
    lock = read_lock(pep.library_lock_path(env={}))
    assert "ghost" not in lock.skills


def test_add_npm_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    pea.add(source="npm:foo", slug=None, env={})
    pea.add(source="npm:foo", slug=None, env={})
    lock = read_lock(pep.library_lock_path(env={}))
    assert list(lock.skills) == ["foo"]
