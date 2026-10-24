"""Native-scope integration: catches destructive toggles and inheritance errors."""
import json

import pytest

from agent_toolkit_cli import pi_npm
from agent_toolkit_cli._pi_settings import PiSettingsError
from tests.pi_npm_fixtures import seed_package, write_json


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_NPM_GLOBAL_ROOT", str(tmp_path / "legacy"))
    home, project = tmp_path / "home", tmp_path / "project"
    root = seed_package(home, project)
    project.mkdir(parents=True, exist_ok=True)
    return home, project, root


def state(home, project):
    return pi_npm.read_npm_states(home=home, project=project)["demo"]


def toggle(home, project, enabled, scope="global", **kwargs):
    pi_npm.set_npm_enabled(identity="demo", enabled=enabled, scope=scope, home=home, project=project, **kwargs)


def test_global_disable_keeps_declaration_files_and_bundled_resources(setup):
    home, project, root = setup
    config = home / ".pi/agent/settings.json"
    original = ["npm:keep", {"source": "npm:demo@1.0.0", "skills": [], "prompts": ["review.md"], "themes": [], "futureField": 123}]
    write_json(config, {"packages": original, "other": {"unchanged": True}})
    before = (root / "extensions/main.ts").read_bytes()
    toggle(home, project, False)
    result = json.loads(config.read_text())
    assert result["packages"] == ["npm:keep", {**original[1], "extensions": []}]
    assert result["other"] == {"unchanged": True}
    assert (root / "extensions/main.ts").read_bytes() == before
    assert not state(home, project).global_scope.enabled
    assert not state(home, project).project_scope.enabled
    toggle(home, project, True)
    assert state(home, project).global_scope.enabled


def test_project_override_can_invert_global_and_reset_without_duplicate_install(setup):
    home, project, root = setup
    global_config = home / ".pi/agent/settings.json"
    original = global_config.read_bytes()
    toggle(home, project, False, "project")
    current = state(home, project)
    assert current.global_scope.enabled and not current.project_scope.enabled
    assert current.project_scope.mode == "override"
    assert global_config.read_bytes() == original
    assert not (project / ".pi/npm").exists()
    toggle(home, project, False)
    toggle(home, project, True, "project")
    current = state(home, project)
    assert not current.global_scope.enabled and current.project_scope.enabled
    pi_npm.reset_npm_override(identity="demo", scope="project", home=home, project=project)
    current = state(home, project)
    assert current.project_scope.mode == "inherit"
    assert not current.project_scope.enabled
    toggle(home, project, True)
    assert state(home, project).project_scope.enabled


@pytest.mark.parametrize("scope", ["global", "project"])
def test_off_survives_new_and_hidden_entrypoints(setup, scope):
    home, project, root = setup
    toggle(home, project, False, scope)
    manifest = json.loads((root / "package.json").read_text())
    for name in ("extensions/new.ts", "extensions/.hidden.ts"):
        (root / name).write_text("throw new Error('never execute')")
        manifest["pi"]["extensions"].append(name)
    write_json(root / "package.json", manifest)
    current = state(home, project).for_scope(scope)
    assert len(current.resources) == 3
    assert not current.enabled and not current.mixed
    toggle(home, project, True, scope)
    assert state(home, project).for_scope(scope).enabled


def test_reset_project_owned_package_preserves_its_version_and_install(setup):
    home, project, root = setup
    project_root = seed_package(home, project, scope="project", version="2.0.0")
    toggle(home, project, False, "project")
    assert state(home, project).global_scope.enabled
    pi_npm.reset_npm_override(identity="demo", scope="project", home=home, project=project)
    current = state(home, project)
    assert current.project_scope.version == "2.0.0"
    assert current.project_scope.mode == "owned"
    assert current.project_scope.enabled
    assert project_root.exists()


def test_busy_lock_and_stale_snapshot_never_write(setup):
    home, project, root = setup
    config = home / ".pi/agent/settings.json"
    snapshot = state(home, project).snapshot
    lock = config.with_name("settings.json.lock")
    lock.mkdir()
    before = config.read_bytes()
    with pytest.raises(PiSettingsError, match="locked"):
        toggle(home, project, False)
    assert config.read_bytes() == before
    lock.rmdir()
    write_json(config, {"packages": [{"source": "npm:demo@1.0.0", "extensions": []}]})
    before = config.read_bytes()
    with pytest.raises(PiSettingsError, match="changed"):
        toggle(home, project, False, expected_snapshot=snapshot)
    assert config.read_bytes() == before


def test_enable_missing_requires_explicit_install_without_writing(setup):
    home, project, root = setup
    import shutil
    shutil.rmtree(root)
    config = home / ".pi/agent/settings.json"
    before = config.read_bytes()
    with pytest.raises(PiSettingsError, match="install"):
        toggle(home, project, True)
    assert config.read_bytes() == before


def test_enable_unconfigured_files_does_not_activate_other_resource_types(setup):
    home, project, root = setup
    write_json(home / ".pi/agent/settings.json", {"packages": []})
    toggle(home, project, True)
    record = state(home, project).global_scope.record
    assert record["skills"] == [] and record["prompts"] == [] and record["themes"] == []
    assert state(home, project).global_scope.enabled


def test_reset_owned_autoload_false_keeps_its_project_declaration(setup):
    home, project, root = setup
    write_json(home / ".pi/agent/settings.json", {"packages": []})
    seed_package(home, project, scope="project", version="2.0.0")
    write_json(project / ".pi/settings.json", {"packages": [{"source": "npm:demo@2.0.0", "autoload": False, "extensions": ["+extensions/main.ts"]}]})
    pi_npm.reset_npm_override(identity="demo", scope="project", home=home, project=project)
    assert state(home, project).project_scope.record == {"source": "npm:demo@2.0.0", "autoload": False}


def test_project_overlay_does_not_hide_a_separate_unused_installation(setup):
    home, project, root = setup
    project_root = seed_package(home, project, scope="project", version="2.0.0")
    write_json(project / ".pi/settings.json", {"packages": [{"source": "npm:demo@2.0.0", "autoload": False, "extensions": ["+extensions/main.ts"]}]})
    current = state(home, project).project_scope
    assert current.root == root and current.version == "1.0.0"
    assert current.scope_root == project_root and current.scope_version == "2.0.0"


def test_reset_delta_preserves_other_resource_overrides(setup):
    home, project, root = setup
    config = project / ".pi/settings.json"
    write_json(config, {"packages": [{"source": "npm:demo@1.0.0", "autoload": False, "skills": ["-skills/review"], "extensions": ["-extensions/main.ts"]}]})
    pi_npm.reset_npm_override(identity="demo", scope="project", home=home, project=project)
    assert json.loads(config.read_text())["packages"] == [{"source": "npm:demo@1.0.0", "autoload": False, "skills": ["-skills/review"]}]
    assert state(home, project).project_scope.enabled
