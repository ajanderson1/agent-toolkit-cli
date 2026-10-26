"""Catalogue Pi acquisition must validate real packaging before registration."""
import json

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from tests.test_cli.test_asset_catalog import entry
from tests.test_cli.test_asset_catalog_acquire import subscribe
from tests.test_cli.test_reground import sandbox, repo, git, invoke


@pytest.mark.parametrize("shape", ["missing", "symlink-entry", "unsafe-pattern", "symlink-manifest"])
def test_bad_pi_content_never_registers_or_projects(tmp_path, sandbox, shape):
    files = {"README.md": "This is not an extension"}
    if shape == "unsafe-pattern":
        files["package.json"] = json.dumps({"pi": {"extensions": ["../outside.ts"]}})
    if shape == "symlink-manifest":
        files["index.ts"] = "throw new Error('must not execute')"
    source = repo(tmp_path, files)
    if shape == "symlink-entry":
        (source / "index.ts").symlink_to("README.md")
    if shape == "symlink-manifest":
        outside = tmp_path / "outside-package.json"
        outside.write_text(json.dumps({"pi": {"extensions": ["index.ts"]}}))
        (source / "package.json").symlink_to(outside)
    if shape.startswith("symlink"):
        git(source, "add", ".")
        git(source, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "unsafe entry")
    subscribe(tmp_path, entry("pi-extension", source=source.as_uri()))
    result = CliRunner().invoke(main, ["pi-extensions", "catalog", "enable", "reviewer", "--scope", "global"])
    assert result.exit_code != 0
    lock = sandbox / ".agent-toolkit/pi-extensions-lock.json"
    assert not lock.exists() or not json.loads(lock.read_text())["skills"]
    assert not (sandbox / ".pi/agent/extensions/reviewer").exists()


def test_pi_declared_regular_entrypoints_are_supported(tmp_path, sandbox):
    source = repo(tmp_path, {
        "package.json": json.dumps({"pi": {"extensions": ["./extensions/*.ts"]}}),
        "extensions/tool.ts": "throw new Error('must not execute')",
    })
    subscribe(tmp_path, entry("pi-extension", source=source.as_uri()))
    invoke("pi-extensions", "catalog", "enable", "reviewer", "--scope", "global")
    assert (sandbox / ".pi/agent/extensions/reviewer/extensions/tool.ts").is_file()


def test_existing_pi_with_removed_entrypoint_retains_edits_and_stays_disabled(tmp_path, sandbox):
    source = repo(tmp_path, {"index.ts": "export default () => {}"})
    subscribe(tmp_path, entry("pi-extension", source=source.as_uri()))
    invoke("pi-extensions", "catalog", "add", "reviewer")
    canonical = sandbox / ".agent-toolkit/pi-extensions/reviewer"
    original = git(canonical, "rev-parse", "HEAD")
    (canonical / "index.ts").unlink()
    (canonical / "local-note.txt").write_text("keep")
    result = CliRunner().invoke(main, ["pi-extensions", "catalog", "enable", "reviewer", "--scope", "global"])
    assert result.exit_code != 0
    assert not (sandbox / ".pi/agent/extensions/reviewer").exists()
    assert git(canonical, "rev-parse", "HEAD") == original
    assert (canonical / "local-note.txt").read_text() == "keep"
    assert not (canonical / "index.ts").exists()
