"""Explicit Git checks for newly catalogued kinds; never content updates."""
import importlib
import json

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from tests.test_cli.test_asset_catalog import entry
from tests.test_cli.test_asset_catalog_acquire import subscribe
from tests.test_cli.test_reground import sandbox, repo, git, invoke


@pytest.mark.parametrize("kind,group,files", [
    ("agent", "agents", {"reviewer.md": "Role"}),
    ("command", "commands", {"COMMAND.md": "Prompt"}),
    ("pi-extension", "pi-extensions", {"index.ts": "export default () => {}"}),
])
def test_git_checks_preserve_local_work_and_survive_unsubscription(tmp_path, sandbox, kind, group, files):
    source = repo(tmp_path, files)
    subscribe(tmp_path, entry(kind, source=source.as_uri()))
    invoke(group, "catalog", "add", "reviewer")
    backing = sandbox / ".agent-toolkit" / group / "reviewer"
    head = git(backing, "rev-parse", "HEAD")
    (backing / "local-note").write_text("keep")
    (source / "upstream-note").write_text("new")
    git(source, "add", ".")
    git(source, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "upstream")
    invoke("catalog", "unsubscribe")
    rows = json.loads(invoke(group, "check", "reviewer", "-g", "--json").output)
    assert rows[0]["status"] == "different" and rows[0]["local_changes"]
    assert rows[0]["local_sha"] == head and rows[0]["checked_at"]
    assert git(backing, "rev-parse", "HEAD") == head
    from agent_toolkit_cli.asset_update_check import read_check
    assert read_check(kind, "reviewer", scope="global", home=sandbox, project=None)["status"] == "different"


def test_new_git_check_commands_have_empty_scope_noop(sandbox):
    assert json.loads(invoke("agents", "check", "-g", "--json").output) == []
    assert json.loads(invoke("commands", "check", "-g", "--json").output) == []
    assert not (sandbox / ".agent-toolkit/agents-update-checks.json").exists()
    assert not (sandbox / ".agent-toolkit/commands-update-checks.json").exists()


def test_git_check_rejects_explicit_native_identity_without_writes(tmp_path, sandbox):
    result = CliRunner().invoke(main, ["pi-extensions", "check", "npm:@example/tools", "-g", "--json"])
    assert result.exit_code != 0 and "native" in result.output.lower()
    assert not (sandbox / ".agent-toolkit/pi-extensions-update-checks.json").exists()
