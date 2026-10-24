"""Native npm add is already install: bundle dispatch must not activate globally."""
import json

import pytest

from agent_toolkit_cli.bundle_dispatch import install_member, uninstall_member, DispatchError
from agent_toolkit_cli.bundle_manifest import BundleMember
from tests.test_cli.test_pi_npm_lifecycle import local_source
from tests.pi_npm_fixtures import write_json


def test_project_bundle_installs_once_in_project_and_rollback_stays_there(local_source):
    home, project, source = local_source
    before = (home / ".pi/agent/settings.json").read_bytes()
    member = BundleMember(asset_type="pi-extension", source=source)
    install_member(member, "project", str(project))
    package = project / ".pi/npm/node_modules/native-local-demo"
    assert package.exists()
    assert (home / ".pi/agent/settings.json").read_bytes() == before
    assert not (home / ".pi/agent/npm").exists()
    assert install_member(member, "project", str(project)) == "already_present"
    uninstall_member(member, scope="project", project_root=str(project))
    assert not package.exists()
    assert (home / ".pi/agent/settings.json").read_bytes() == before


def test_bundle_refuses_to_modify_a_preexisting_unconfigured_native_module(local_source):
    from tests.pi_npm_fixtures import seed_package
    home, project, source = local_source
    root = seed_package(home, project, scope="project", name="native-local-demo", configured=False)
    before = (root / "package.json").read_bytes()
    with pytest.raises(DispatchError, match="existing|preexisting"):
        install_member(BundleMember(asset_type="pi-extension", source=source), "project", str(project))
    assert (root / "package.json").read_bytes() == before
    assert not (home / ".pi/agent/npm").exists()


def test_import_skips_legacy_npm_records_instead_of_recreating_catalogue(local_source, tmp_path):
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main
    home, project, source = local_source
    incoming = tmp_path / "incoming.json"
    write_json(incoming, {"version": 1, "skills": {"old": {"source": source, "sourceType": "npm"}}})
    result = CliRunner().invoke(main, ["pi-extensions", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "skipped" in result.output and "npm" in result.output
    assert not (home / ".agent-toolkit/pi-extensions-lock.json").exists()
    assert not (home / ".pi/agent/npm").exists()
