"""Catches catalogue ghosts, false enablement and lossy native package parsing."""
import json
from pathlib import Path

import pytest

from agent_toolkit_cli import _pi_settings
from agent_toolkit_cli.pi_extension_inventory import build_inventory
from tests.pi_npm_fixtures import seed_package, write_json


@pytest.fixture(autouse=True)
def isolated_legacy(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_TOOLKIT_NPM_GLOBAL_ROOT", str(tmp_path / "legacy"))


def test_mixed_native_packages_preserve_entry_forms_and_filters(tmp_path):
    path = tmp_path / ".pi/agent/settings.json"
    original = ["npm:keep", {"source": "npm:filtered", "extensions": [], "skills": ["+skill"], "futureField": {"kept": True}}]
    write_json(path, {"packages": original, "other": 42})
    assert _pi_settings.read_packages(scope="global", home=tmp_path) == ["npm:keep", "npm:filtered"]
    _pi_settings.add_package("npm:new", scope="global", home=tmp_path)
    actual = json.loads(path.read_text())
    assert actual["packages"][:2] == original
    assert actual["other"] == 42


def test_registration_without_native_footprint_disappears(tmp_path, monkeypatch):
    from agent_toolkit_cli.pi_extension_lock import LockEntry, LockFile, write_lock
    from agent_toolkit_cli.pi_extension_paths import library_lock_path
    monkeypatch.setenv("HOME", str(tmp_path))
    path = library_lock_path(env={})
    write_lock(path, LockFile(version=1, skills={"ghost": LockEntry(source="npm:ghost", source_type="npm")}))
    before = path.read_bytes()
    assert "ghost" not in {r.slug for r in build_inventory(home=tmp_path)}
    assert path.read_bytes() == before


def test_direct_install_without_settings_is_available_not_enabled(tmp_path):
    home, project = tmp_path / "home", tmp_path / "project"
    root = seed_package(home, project, configured=False)
    rows = {r.slug: r for r in build_inventory(home=home, project=project)}
    assert "demo" in rows
    assert rows["demo"].global_loaded is False
    assert rows["demo"].npm_state.global_scope.root == root
    assert rows["demo"].npm_state.global_scope.configured is False


def test_native_npm_identity_does_not_include_version(tmp_path):
    home, project = tmp_path / "home", tmp_path / "project"
    seed_package(home, project, name="@scope/demo", version="1.0.0")
    rows = {r.slug: r for r in build_inventory(home=home, project=project)}
    assert "@scope/demo" in rows
    row = rows["@scope/demo"]
    assert row.global_loaded and row.project_loaded
    assert row.npm_state.project_scope.mode == "inherit"
    assert row.project_package_spec is None
    assert row.project_config_path is None
    assert row.npm_state.global_scope.version == "1.0.0"


def test_transitive_files_do_not_make_an_inventory_row(tmp_path):
    home, project = tmp_path / "home", tmp_path / "project"
    root = seed_package(home, project, configured=False)
    write_json(root.parent / "transitive/package.json", {"name": "transitive", "version": "1.0.0", "pi": {"extensions": ["index.js"]}})
    (root.parent / "transitive/index.js").write_text("throw new Error('never execute')")
    assert [r.slug for r in build_inventory(home=home, project=project)] == ["demo"]


def test_available_install_keeps_its_local_source_not_a_registry_guess(tmp_path):
    from agent_toolkit_cli.pi_npm import read_npm_states
    home, project = tmp_path / "home", tmp_path / "project"
    seed_package(home, project, configured=False)
    write_json(home / ".pi/agent/npm/package.json", {"dependencies": {"demo": "file:/private/local-demo"}})
    current = read_npm_states(home=home, project=project)["demo"]
    assert current.global_scope.source == "npm:demo@file:/private/local-demo"


def test_native_identity_cannot_disappear_as_a_javascript_prototype_key(tmp_path):
    home, project = tmp_path / "home", tmp_path / "project"
    seed_package(home, project, name="__proto__")
    assert "__proto__" in {r.slug for r in build_inventory(home=home, project=project)}


def test_configured_missing_source_remains_visible_without_fetch(tmp_path):
    home = tmp_path / "home"
    config = home / ".pi/agent/settings.json"
    write_json(config, {"packages": ["npm:missing@1.0.0"]})
    before = config.read_bytes()
    row = next(r for r in build_inventory(home=home) if r.slug == "missing")
    assert row.npm_state.global_scope.missing
    assert not row.global_loaded
    assert not (config.parent / "npm").exists()
    assert config.read_bytes() == before
