"""Native Pi local selectors: configuration changes never own the resources."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_toolkit_cli._pi_settings import PiSettingsError
from agent_toolkit_cli.pi_extension_inventory import build_inventory
from agent_toolkit_tui.pi_extension_state import build_pi_rows


@pytest.fixture
def local(tmp_path, monkeypatch):
    home, project = tmp_path / "home", tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    path = home / ".pi/agent/extensions/router.ts"
    path.parent.mkdir(parents=True)
    path.write_text("export default () => {}")
    return home, project, path


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def read(home, project):
    from agent_toolkit_cli.pi_local_extensions import read_local_extension_state
    return read_local_extension_state(slug="router", home=home, project=project)


def toggle(home, project, paths, enabled, scope="global"):
    from agent_toolkit_cli.pi_local_extensions import set_local_extension_enabled
    set_local_extension_enabled(
        slug="router", home=home, project=project, scope=scope,
        enabled=enabled, expected_paths=tuple(paths),
    )


def test_default_discovery_is_enabled_including_project_inheritance(local):
    home, project, path = local
    row, = build_pi_rows(home=home, project=project)
    assert row.global_cell.global_loaded is True
    assert row.project_cell.project_loaded is True
    assert not row.managed


@pytest.mark.parametrize("selectors,want", [
    ([], True), (["other/*.ts"], True), (["!**/*.ts"], False),
    (["!router.ts"], False), (["!!extensions/router.ts"], False), (["!**/{router,other}.ts"], False),
    (["!**/@(router|other).ts"], False),
    (["!**/*.ts", "+extensions/router.ts"], True),
    (["-extensions/router.ts", "+extensions/router.ts"], False),
    (["+extensions/router.ts", "-extensions/router.ts"], False),
    (["-router.ts"], True), (["-extensions/*.ts"], True),
])
def test_selector_classes_follow_native_precedence(local, selectors, want):
    home, project, _ = local
    put(home / ".pi/agent/settings.json", {"extensions": selectors})
    state = read(home, project)
    assert state.global_enabled is want
    assert state.project_enabled is want


def test_project_signed_selector_requires_plain_inherited_reference(local):
    home, project, path = local
    settings = project / ".pi/settings.json"
    put(settings, {"extensions": [f"-{path}"]})
    assert read(home, project).project_enabled is True
    put(settings, {"extensions": [str(path), f"-{path}"]})
    state = read(home, project)
    assert state.global_enabled is True
    assert state.project_enabled is False


@pytest.mark.parametrize("scope", ["global", "project"])
def test_disable_enable_idempotence_preserves_sources_and_unrelated_settings(local, scope):
    home, project, path = local
    settings = home / ".pi/agent/settings.json" if scope == "global" else project / ".pi/settings.json"
    keep = {"theme": "light", "packages": [{"source": "npm:keep", "skills": []}], "skills": ["untouched"], "extensions": ["!**/other.ts"]}
    put(settings, keep)
    source = path.read_bytes()
    lock = home / ".agent-toolkit/pi-extensions-lock.json"
    put(lock, {"version": 1, "skills": {}})
    lock_before = lock.read_bytes()
    for enabled in (False, True):
        toggle(home, project, [path], enabled, scope)
        result = json.loads(settings.read_text())
        pattern = "extensions/router.ts" if scope == "global" else str(path)
        want = ["!**/other.ts", *([str(path)] if scope == "project" else []), ("+" if enabled else "-") + pattern]
        assert result == {**keep, "extensions": want}
        before = settings.read_bytes()
        toggle(home, project, [path], enabled, scope)
        assert settings.read_bytes() == before
        state = read(home, project)
        assert state.project_enabled is enabled
        assert state.global_enabled is (enabled if scope == "global" else True)
    assert path.read_bytes() == source
    assert lock.read_bytes() == lock_before


def test_manifest_mixed_state_and_whole_directory_toggle(local):
    home, project, old = local
    old.unlink()
    directory = old.with_suffix("")
    directory.mkdir()
    a, b = directory / "a.ts", directory / "b.ts"
    a.write_text("a")
    b.write_text("b")
    put(directory / "package.json", {"pi": {"extensions": ["a.ts", "b.ts"]}})
    put(home / ".pi/agent/settings.json", {"extensions": ["-extensions/router/a.ts"]})
    state = read(home, project)
    assert [(entry.path, entry.enabled) for entry in state.global_entries] == [(a, False), (b, True)]
    assert state.global_mixed and not state.global_enabled
    toggle(home, project, [a, b], True)
    assert read(home, project).global_enabled is True
    assert a.read_text() == "a" and b.read_text() == "b"


@pytest.mark.parametrize("change", ["vanished", "added", "malformed", "invalid-list", "busy"])
def test_invalid_or_stale_intent_never_writes_settings(local, change):
    home, project, path = local
    settings = home / ".pi/agent/settings.json"
    put(settings, {"theme": "preserve", "extensions": []})
    if change == "vanished":
        path.unlink()
    elif change == "added":
        path.with_suffix(".js").write_text("new")
    elif change == "malformed":
        settings.write_text("{invalid")
    elif change == "invalid-list":
        put(settings, {"extensions": "not a list"})
    else:
        Path(str(settings) + ".lock").mkdir()
    before = settings.read_bytes()
    with pytest.raises(PiSettingsError):
        toggle(home, project, [path], False)
    assert settings.read_bytes() == before
    if change != "busy":
        assert not Path(str(settings) + ".lock").exists()


def test_rereads_current_settings_after_acquiring_native_lock(local, monkeypatch):
    home, project, path = local
    settings = home / ".pi/agent/settings.json"
    put(settings, {"theme": "old"})
    native_mkdir = Path.mkdir
    def concurrent_edit(self, *args, **kwargs):
        if self == Path(str(settings) + ".lock"):
            put(settings, {"theme": "concurrently changed", "skills": ["keep"]})
        return native_mkdir(self, *args, **kwargs)
    monkeypatch.setattr(Path, "mkdir", concurrent_edit)
    toggle(home, project, [path], False)
    assert json.loads(settings.read_text()) == {
        "theme": "concurrently changed", "skills": ["keep"], "extensions": ["-extensions/router.ts"],
    }


@pytest.mark.parametrize("manifest", [{}, {"pi": {"extensions": []}}, {"pi": {"extensions": ["missing.ts"]}}, {"pi": {"extensions": [123]}}])
def test_package_json_alone_is_not_a_discovered_extension(local, manifest):
    home, project, path = local
    path.unlink()
    put(path.with_suffix("") / "package.json", manifest)
    assert build_inventory(home=home, project=project) == []
    (path.with_suffix("") / "index.js").write_text("fallback")
    assert [r.slug for r in build_inventory(home=home, project=project)] == ["router"]


def test_native_root_index_and_ignore_rules_define_discovery(local):
    home, project, path = local
    (path.parent / ".hidden.ts").write_text("hidden")
    (path.parent / "ignored.ts").write_text("ignored")
    (path.parent / ".gitignore").write_text("ignored.ts\n")
    assert [r.slug for r in build_inventory(home=home, project=project)] == ["router"]
    (path.parent / "index.ts").write_text("index")
    assert [r.slug for r in build_inventory(home=home, project=project)] == ["index"]


def test_symlink_selectors_use_lexical_path_and_native_dedup(local, tmp_path):
    home, project, path = local
    path.unlink()
    target = tmp_path / "target.ts"
    target.write_text("source")
    path.symlink_to(target)
    alias = path.with_name("second.ts")
    alias.symlink_to(target)
    put(home / ".pi/agent/settings.json", {"extensions": [f"-{target}"]})
    assert read(home, project).global_enabled is True
    assert [r.slug for r in build_inventory(home=home, project=project)] == ["router"]
    toggle(home, project, [path], False)
    assert path.is_symlink() and target.read_text() == "source"
    assert read(home, project).global_enabled is False
    assert json.loads((home / ".pi/agent/settings.json").read_text())["extensions"] == [f"-{target}", "-extensions/router.ts"]


def test_native_bom_settings_remain_editable(local):
    home, project, path = local
    settings = home / ".pi/agent/settings.json"
    settings.write_text('\ufeff' + json.dumps({"theme": "keep"}))
    toggle(home, project, [path], False)
    assert json.loads(settings.read_text()) == {"theme": "keep", "extensions": ["-extensions/router.ts"]}


def test_settings_symlink_and_permissions_survive_toggle(local, tmp_path):
    home, project, path = local
    target = tmp_path / "private-settings.json"
    put(target, {"theme": "keep"})
    target.chmod(0o600)
    settings = home / ".pi/agent/settings.json"
    settings.symlink_to(target)
    toggle(home, project, [path], False)
    assert settings.is_symlink()
    assert target.stat().st_mode & 0o777 == 0o600
    assert json.loads(target.read_text()) == {"theme": "keep", "extensions": ["-extensions/router.ts"]}


def test_project_can_enable_a_globally_disabled_resource(local):
    home, project, path = local
    put(home / ".pi/agent/settings.json", {"extensions": ["-extensions/router.ts"]})
    toggle(home, project, [path], True, "project")
    state = read(home, project)
    assert not state.global_enabled and state.project_enabled


def test_project_local_can_be_selected_globally_without_copying(local):
    home, project, path = local
    path.unlink()
    local_file = project / ".pi/extensions/router.ts"
    local_file.parent.mkdir(parents=True)
    local_file.write_text("source")
    assert not read(home, project).global_enabled
    toggle(home, project, [local_file], True)
    assert read(home, project).global_enabled
    assert local_file.read_text() == "source"
    assert json.loads((home / ".pi/agent/settings.json").read_text())["extensions"] == [str(local_file), f"+{local_file}"]
