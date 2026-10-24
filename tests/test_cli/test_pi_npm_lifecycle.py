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


@pytest.mark.parametrize("scope", ["global", "project"])
def test_removal_reports_actual_remaining_scope_and_global_fallback(local_source, tmp_path, scope):
    from agent_toolkit_cli import pi_npm
    from agent_toolkit_cli.pi_npm_lifecycle import install_npm, remove_npm
    home, project, source = local_source
    second = tmp_path / "source-v2"
    write_json(second / "package.json", {"name": "native-local-demo", "version": "2.0.0", "pi": {"extensions": ["index.ts"]}})
    (second / "index.ts").write_text("throw new Error('Never execute extension code')")
    install_npm(source=source, scope="global", home=home, project=project)
    install_npm(source="npm:native-local-demo@file:" + str(second), scope="project", home=home, project=project)
    other = "project" if scope == "global" else "global"
    before = pi_npm.read_npm_states(home=home, project=project)["native-local-demo"].for_scope(other)
    metadata = (before.scope_root / "package.json").read_bytes()
    result = remove_npm(identity="native-local-demo", scope=scope, home=home, project=project)
    after = pi_npm.read_npm_states(home=home, project=project)["native-local-demo"]
    assert result.files_removed and result.other_scope_configured
    assert after.for_scope(other).enabled
    assert (before.scope_root / "package.json").read_bytes() == metadata
    assert result.fallback_status == ("Enabled" if scope == "project" else None)
    if scope == "project":
        assert after.project_scope.mode == "inherit" and after.project_scope.enabled
    assert (tmp_path / "source/index.ts").exists() and (second / "index.ts").exists()


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


@pytest.mark.parametrize("verb", ["install", "remove", "uninstall"])
@pytest.mark.parametrize("slug", ["old-alias", "old#alias"])
def test_legacy_only_slugs_do_not_grant_native_lifecycle_authority(local_source, verb, slug):
    home, project, source = local_source
    lock = home / ".agent-toolkit/pi-extensions-lock.json"
    write_json(lock, {"version": 1, "skills": {slug: {"source": source, "sourceType": "npm"}}})
    before = lock.read_bytes()
    result = CliRunner().invoke(main, ["pi-extensions", verb, slug] + (["--yes"] if verb != "install" else []))
    assert result.exit_code != 0, result.output
    assert "retired" in result.output or "native identity" in result.output
    assert not (home / ".pi/agent/npm").exists()
    assert lock.read_bytes() == before


@pytest.mark.parametrize("aged", [False, True])
def test_external_removal_refuses_busy_settings_before_deleting_files(local_source, tmp_path, monkeypatch, aged):
    import shutil
    import subprocess
    from agent_toolkit_cli.pi_npm_lifecycle import remove_npm
    from agent_toolkit_cli._pi_settings import PiSettingsError
    home, project, source = local_source
    prefix = tmp_path / "external-prefix"
    root = prefix / "lib/node_modules"
    subprocess.run([shutil.which("npm"), "install", "--global", "--prefix", str(prefix), source.removeprefix("npm:")], check=True, capture_output=True, text=True)
    monkeypatch.setenv("AGENT_TOOLKIT_NPM_GLOBAL_ROOT", str(root))
    config = home / ".pi/agent/settings.json"
    write_json(config, {"packages": ["npm:native-local-demo"]})
    lock = config.with_name(config.name + ".lock"); lock.mkdir()
    if aged:
        import os
        os.utime(lock, (0, 0))  # Even an old lock must not be stolen.
    before = config.read_bytes()
    with pytest.raises(PiSettingsError, match="locked"):
        remove_npm(identity="native-local-demo", scope="global", home=home, project=project, external=True)
    assert (root / "native-local-demo/package.json").exists()
    assert config.read_bytes() == before and lock.is_dir()


def test_external_lock_heartbeats_and_interoperates_with_native_proper_lockfile(local_source):
    import os
    import shutil
    import subprocess
    import time
    from agent_toolkit_cli import pi_npm
    from agent_toolkit_cli.pi_npm_lifecycle import _external_settings_lock
    home, project, _ = local_source
    config = home / ".pi/agent/settings.json"
    lock = config.with_name(config.name + ".lock")
    native = pi_npm._pi_root(os.environ.get("AGENT_TOOLKIT_PI_PACKAGE"), shutil.which("pi"))
    code = '''import {createRequire} from 'node:module';
const require=createRequire(process.argv[1]+'/package.json');
const lockfile=require('proper-lockfile');
try { const release=await lockfile.lock(process.argv[2],{realpath:false,stale:2000,retries:0}); await release(); console.log('stolen'); }
catch(error) { if(error.code!=='ELOCKED') throw error; console.log('blocked'); }'''
    with _external_settings_lock(config) as check:
        initial = lock.stat().st_mtime_ns
        time.sleep(2.3)
        check()
        assert lock.stat().st_mtime_ns > initial
        contender = subprocess.run([shutil.which("node"), "--input-type=module", "-e", code, str(native), str(config)], capture_output=True, text=True, check=True)
        assert contender.stdout.strip() == "blocked"
    assert not lock.exists()


@pytest.mark.parametrize("surface", ["api", "remove", "uninstall"])
def test_removal_reports_files_retained_as_another_packages_dependency(local_source, tmp_path, surface):
    import shutil
    import subprocess
    from agent_toolkit_cli.pi_npm_lifecycle import install_npm, remove_npm
    home, project, source = local_source
    packed = tmp_path / "packed"; packed.mkdir()
    npm = shutil.which("npm")
    first = subprocess.run([npm, "pack", "--ignore-scripts", "--pack-destination", str(packed), str(tmp_path / "source")], check=True, capture_output=True, text=True)
    tarball = packed / first.stdout.strip().splitlines()[-1]
    consumer = tmp_path / "consumer"
    write_json(consumer / "package.json", {"name": "native-consumer", "version": "1.0.0", "dependencies": {"native-local-demo": "file:" + str(tarball)}})
    second = subprocess.run([npm, "pack", "--ignore-scripts", "--pack-destination", str(packed), str(consumer)], check=True, capture_output=True, text=True)
    consumer_tarball = packed / second.stdout.strip().splitlines()[-1]
    install_npm(source="npm:native-local-demo@file:" + str(tarball), scope="global", home=home, project=project)
    install_npm(source="npm:native-consumer@file:" + str(consumer_tarball), scope="global", home=home, project=project)
    package = home / ".pi/agent/npm/node_modules/native-local-demo"
    if surface == "api":
        result = remove_npm(identity="native-local-demo", scope="global", home=home, project=project)
        assert result.files_remain and not result.files_removed
        assert result.declaration_removed and result.direct_removed
        repeated = remove_npm(identity="native-local-demo", scope="global", home=home, project=project)
        assert repeated.files_remain and "files remain" in repeated.describe()
        assert not repeated.declaration_removed and not repeated.direct_removed
    else:
        result = CliRunner().invoke(main, ["pi-extensions", surface, "native-local-demo", "--yes"])
        assert result.exit_code == 0, result.output
        assert "files remain" in result.output
        assert "package files removed" not in result.output
    assert package.exists()
    dependencies = json.loads((home / ".pi/agent/npm/package.json").read_text())["dependencies"]
    assert "native-local-demo" not in dependencies and "native-consumer" in dependencies


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
