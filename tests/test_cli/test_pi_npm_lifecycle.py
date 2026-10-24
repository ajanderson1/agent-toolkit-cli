"""Exercise the real Pi/npm CLI offline with local packages and disposable HOME."""
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from tests.pi_npm_fixtures import write_json


@pytest.fixture
def local_source(tmp_path, monkeypatch):
    home, project, source = tmp_path / "home", tmp_path / "project", tmp_path / "source"
    home.mkdir(); project.mkdir(); source.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENT_TOOLKIT_NPM_GLOBAL_ROOT", str(tmp_path / "legacy"))
    monkeypatch.setenv("NPM_CONFIG_IGNORE_SCRIPTS", "true")
    monkeypatch.setenv("NPM_CONFIG_AUDIT", "false")
    monkeypatch.setenv("NPM_CONFIG_FUND", "false")
    monkeypatch.delenv("PI_OFFLINE", raising=False)
    monkeypatch.chdir(project)
    write_json(home / ".pi/agent/settings.json", {"defaultProjectTrust": "always"})
    write_json(source / "package.json", {"name": "native-local-demo", "version": "1.0.0", "pi": {"extensions": ["index.ts"]}})
    (source / "index.ts").write_text("throw new Error('Never execute extension code')")
    return home, project, f"npm:native-local-demo@file:{source}"


@pytest.mark.parametrize("verb", ["add", "install"])
@pytest.mark.parametrize("project_scope", [False, True])
def test_add_install_delegate_native_install_without_toolkit_registration(local_source, verb, project_scope):
    home, project, source = local_source
    result = CliRunner().invoke(main, ["pi-extensions", verb, source] + (["-p"] if project_scope else []))
    assert result.exit_code == 0, result.output
    base = project / ".pi" if project_scope else home / ".pi/agent"
    assert source in [p if isinstance(p, str) else p["source"] for p in json.loads((base / "settings.json").read_text())["packages"]]
    assert (base / "npm/node_modules/native-local-demo/package.json").exists()
    assert not (home / ".agent-toolkit/pi-extensions-lock.json").exists()
    assert not (home / ".agent-toolkit/pi-extensions/native-local-demo").exists()


def test_enable_disable_are_settings_only_and_uninstall_requires_confirmation(local_source):
    home, project, source = local_source
    runner = CliRunner()
    assert runner.invoke(main, ["pi-extensions", "add", source]).exit_code == 0
    package = home / ".pi/agent/npm/node_modules/native-local-demo"
    disabled = runner.invoke(main, ["pi-extensions", "disable", "native-local-demo", "-p"])
    assert disabled.exit_code == 0, disabled.output
    result = runner.invoke(main, ["pi-extensions", "enable", "native-local-demo", "-p"])
    assert result.exit_code == 0, result.output
    assert package.exists()
    assert not (project / ".pi/npm").exists()
    before = package.joinpath("package.json").read_bytes()
    result = runner.invoke(main, ["pi-extensions", "uninstall", "native-local-demo"], input="n\n")
    assert result.exit_code != 0
    assert package.joinpath("package.json").read_bytes() == before
    result = runner.invoke(main, ["pi-extensions", "remove", "native-local-demo", "--yes"])
    assert result.exit_code == 0, result.output
    assert not package.exists()
    assert "packages" not in json.loads((home / ".pi/agent/settings.json").read_text()) or json.loads((home / ".pi/agent/settings.json").read_text())["packages"] == []


def test_native_no_reference_error_after_real_removal_is_not_false_failure(local_source):
    home, project, source = local_source
    runner = CliRunner()
    assert runner.invoke(main, ["pi-extensions", "add", source]).exit_code == 0
    config = home / ".pi/agent/settings.json"
    data = json.loads(config.read_text()); data["packages"] = []; write_json(config, data)
    result = runner.invoke(main, ["pi-extensions", "uninstall", "native-local-demo", "--yes"])
    assert result.exit_code == 0, result.output
    assert not (home / ".pi/agent/npm/node_modules/native-local-demo").exists()


def test_explicit_project_install_allowed_when_global_already_installed(local_source):
    home, project, source = local_source
    runner = CliRunner()
    assert runner.invoke(main, ["pi-extensions", "add", source]).exit_code == 0
    before = (home / ".pi/agent/settings.json").read_bytes()
    result = runner.invoke(main, ["pi-extensions", "install", source, "-p"])
    assert result.exit_code == 0, result.output
    assert (home / ".pi/agent/npm/node_modules/native-local-demo").exists()
    assert (project / ".pi/npm/node_modules/native-local-demo").exists()
    assert (home / ".pi/agent/settings.json").read_bytes() == before


def test_real_installer_failure_is_not_normalized_into_success(local_source):
    from agent_toolkit_cli.pi_npm_lifecycle import remove_npm
    from agent_toolkit_cli._pi_settings import PiSettingsError
    home, project, source = local_source
    runner = CliRunner()
    assert runner.invoke(main, ["pi-extensions", "add", source]).exit_code == 0
    failing = home / "failing-npm.mjs"
    failing.write_text("console.error('fixture uninstall failed');process.exit(9)")
    config = home / ".pi/agent/settings.json"
    data = json.loads(config.read_text()); data["npmCommand"] = ["node", str(failing)]; write_json(config, data)
    before = config.read_bytes()
    with pytest.raises(PiSettingsError, match="fixture uninstall failed"):
        remove_npm(identity="native-local-demo", scope="global", home=home, project=project)
    assert config.read_bytes() == before
    assert (home / ".pi/agent/npm/node_modules/native-local-demo").exists()


def test_native_install_keeps_existing_resource_filters(local_source):
    home, project, source = local_source
    runner = CliRunner()
    assert runner.invoke(main, ["pi-extensions", "add", source]).exit_code == 0
    config = home / ".pi/agent/settings.json"
    data = json.loads(config.read_text())
    data["packages"] = [{"source": source, "extensions": [], "skills": []}]
    write_json(config, data)
    result = runner.invoke(main, ["pi-extensions", "install", source])
    assert result.exit_code == 0, result.output
    assert json.loads(config.read_text())["packages"] == data["packages"]


def test_native_npm_honors_custom_pi_agent_directory(local_source, tmp_path, monkeypatch):
    home, project, source = local_source
    custom = tmp_path / "custom-pi-agent"
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(custom))
    before = (home / ".pi/agent/settings.json").read_bytes()
    runner = CliRunner()
    result = runner.invoke(main, ["pi-extensions", "add", source])
    assert result.exit_code == 0, result.output
    assert (custom / "npm/node_modules/native-local-demo").exists()
    result = runner.invoke(main, ["pi-extensions", "disable", "native-local-demo"])
    assert result.exit_code == 0, result.output
    assert json.loads((custom / "settings.json").read_text())["packages"][0]["extensions"] == []
    assert (home / ".pi/agent/settings.json").read_bytes() == before
    assert not (home / ".pi/agent/npm").exists()


def test_external_npm_removal_uses_the_real_prefix_and_keeps_link_target(local_source, tmp_path, monkeypatch):
    import shutil
    import subprocess
    home, project, source = local_source
    prefix = tmp_path / "external-prefix"
    root = prefix / "lib/node_modules"
    subprocess.run([shutil.which("npm"), "install", "--global", "--prefix", str(prefix), source.removeprefix("npm:")], check=True, capture_output=True, text=True)
    monkeypatch.setenv("AGENT_TOOLKIT_NPM_GLOBAL_ROOT", str(root))
    config = home / ".pi/agent/settings.json"
    before = json.loads(config.read_text())
    write_json(config, {**before, "packages": ["npm:native-local-demo"]})
    runner = CliRunner()
    refused = runner.invoke(main, ["pi-extensions", "remove", "npm:native-local-demo", "--yes"])
    assert refused.exit_code != 0 and "--external" in refused.output
    assert (root / "native-local-demo").exists()
    result = runner.invoke(main, ["pi-extensions", "remove", "npm:native-local-demo", "--external", "--yes"])
    assert result.exit_code == 0, result.output
    assert not (root / "native-local-demo").exists()
    assert (tmp_path / "source/index.ts").exists()
    assert json.loads(config.read_text())["defaultProjectTrust"] == "always"
    assert json.loads(config.read_text())["packages"] == []


def test_external_removal_never_guesses_a_prefix_that_targets_another_folder(local_source, tmp_path, monkeypatch):
    from agent_toolkit_cli.pi_npm_lifecycle import remove_npm
    from agent_toolkit_cli._pi_settings import PiSettingsError
    home, project, source = local_source
    selected = tmp_path / "arbitrary/node_modules"
    sentinel = tmp_path / "arbitrary/lib/node_modules/native-local-demo/package.json"
    write_json(selected / "native-local-demo/package.json", {"name": "native-local-demo", "version": "1.0.0", "pi": {"extensions": ["index.ts"]}})
    (selected / "native-local-demo/index.ts").write_text("throw new Error('never execute')")
    write_json(sentinel, {"name": "native-local-demo", "version": "99.0.0"})
    before = sentinel.read_bytes()
    monkeypatch.setenv("AGENT_TOOLKIT_NPM_GLOBAL_ROOT", str(selected))
    with pytest.raises(PiSettingsError, match="prefix|actual installer"):
        remove_npm(identity="native-local-demo", scope="global", home=home, project=project, external=True)
    assert sentinel.read_bytes() == before
    assert (selected / "native-local-demo").exists()


def test_default_cli_inventory_sees_native_project_packages_without_toolkit_lock(local_source):
    home, project, source = local_source
    runner = CliRunner()
    installed = runner.invoke(main, ["pi-extensions", "add", source, "-p"])
    assert installed.exit_code == 0, installed.output
    result = runner.invoke(main, ["pi-extensions", "list", "--json"])
    assert result.exit_code == 0, result.output
    rows = {row["slug"]: row for row in json.loads(result.output)}
    assert rows["native-local-demo"]["projectLoaded"] is True
    assert not (project / "pi-extensions-lock.json").exists()
    global_only = runner.invoke(main, ["pi-extensions", "list", "-g", "--json"])
    assert "native-local-demo" not in {row["slug"] for row in json.loads(global_only.output)}


def test_reset_selection_cli_restores_global_inheritance_without_removing_files(local_source):
    from agent_toolkit_cli import pi_npm
    home, project, source = local_source
    runner = CliRunner()
    assert runner.invoke(main, ["pi-extensions", "add", source]).exit_code == 0
    before = (home / ".pi/agent/settings.json").read_bytes()
    assert runner.invoke(main, ["pi-extensions", "disable", "native-local-demo", "-p"]).exit_code == 0
    result = runner.invoke(main, ["pi-extensions", "reset-selection", "native-local-demo", "-p"])
    assert result.exit_code == 0, result.output
    current = pi_npm.read_npm_states(home=home, project=project)["native-local-demo"]
    assert current.project_scope.mode == "inherit" and current.project_scope.enabled
    assert (home / ".pi/agent/settings.json").read_bytes() == before
    assert not (project / ".pi/npm").exists()


def test_legacy_migration_is_explicit_backup_only(local_source):
    home, project, source = local_source
    lock = home / ".agent-toolkit/pi-extensions-lock.json"
    original = {"version": 1, "skills": {"old": {"source": "npm:old", "sourceType": "npm"}, "keep": {"source": "owner/keep", "sourceType": "github", "customMetadata": 42}}}
    write_json(lock, original)
    before = lock.read_bytes()
    runner = CliRunner()
    result = runner.invoke(main, ["pi-extensions", "migrate-npm-records"])
    assert result.exit_code == 0, result.output
    assert lock.read_bytes() == before
    result = runner.invoke(main, ["pi-extensions", "migrate-npm-records", "--apply"])
    assert result.exit_code == 0, result.output
    assert json.loads(lock.read_text())["skills"] == {"keep": original["skills"]["keep"]}
    backups = list(lock.parent.glob("*.before-native-npm-*.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == before
    assert not (home / ".pi/agent/npm").exists()
