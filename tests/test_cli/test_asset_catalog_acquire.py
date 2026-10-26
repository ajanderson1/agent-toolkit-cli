"""Catalogue acquisition respects real per-kind backing and exposure boundaries."""
import importlib
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from tests.test_cli.test_asset_catalog import entry, manifest
from tests.test_cli.test_reground import sandbox, repo, git, invoke


def subscribe(tmp_path, *items):
    directory = tmp_path / "catalog"
    directory.mkdir()
    cat = repo(directory, {"catalog.json": json.dumps(manifest(*items))})
    invoke("catalog", "subscribe", cat.as_uri())
    return cat


@pytest.mark.parametrize("kind,group,files", [
    ("agent", "agents", {"reviewer.md": "Review carefully"}),
    ("command", "commands", {"COMMAND.md": "Summarize carefully"}),
    ("pi-extension", "pi-extensions", {"index.ts": "export default () => {}"}),
])
def test_add_and_explicit_project_enable(tmp_path, sandbox, kind, group, files):
    source = repo(tmp_path, files)
    subscribe(tmp_path, entry(kind, source=source.as_uri()))
    project = tmp_path / "project"
    project.mkdir()
    invoke(group, "catalog", "add", "reviewer")
    backing = sandbox / ".agent-toolkit" / group / "reviewer"
    assert backing.is_dir()
    assert not (sandbox / ".pi/agent/extensions/reviewer").exists()
    args = ["--project", str(project), group, "catalog", "enable", "reviewer", "--scope", "project"]
    if kind != "pi-extension":
        args += ["--harnesses", "pi"]
    invoke(*args)
    destination = project / ".pi" / {"agent": "agents/reviewer.md", "command": "prompts/reviewer.md", "pi-extension": "extensions/reviewer"}[kind]
    assert destination.exists()
    lock = json.loads((sandbox / ".agent-toolkit" / f"{group}-lock.json").read_text())
    assert lock["skills"]["reviewer"]["catalog"]["kind"] == kind
    invoke("catalog", "unsubscribe")
    assert destination.exists() and backing.exists()


def test_existing_agent_parent_is_not_advanced_or_cleaned(tmp_path, sandbox):
    source = repo(tmp_path, {"agents/reviewer/reviewer.md": "original", "agents/other/other.md": "sibling"})
    invoke("agents", "add", source.as_uri() + "/tree/main/agents/reviewer", "--slug", "reviewer")
    backing = sandbox / ".agent-toolkit/agents/reviewer"
    old_head = git(backing, "rev-parse", "HEAD")
    (source / "agents/reviewer/reviewer.md").write_text("new upstream")
    git(source, "add", ".")
    git(source, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "advance")
    subscribe(tmp_path, entry(source=source.as_uri(), path="agents/reviewer"))
    (backing / "local-note.txt").write_text("keep")
    invoke("agents", "catalog", "add", "reviewer")
    assert git(backing, "rev-parse", "HEAD") == old_head
    assert (backing / "reviewer.md").read_text() == "original"
    assert (backing / "local-note.txt").read_text() == "keep"


@pytest.mark.parametrize("kind,group,files", [
    ("command", "commands", {"commands/reviewer/COMMAND.md": "Prompt"}),
    ("pi-extension", "pi-extensions", {"index.ts": "export default () => {}"}),
])
def test_same_source_different_ref_refuses_reuse(tmp_path, sandbox, kind, group, files):
    source = repo(tmp_path, files)
    git(source, "tag", "release")
    path = "commands/reviewer" if kind == "command" else "."
    original = source.as_uri() + "/tree/main/commands/reviewer" if kind == "command" else source.as_uri()
    args = [group, "add", original, "--slug", "reviewer"]
    if kind == "command":
        args += ["--ref", "main"]
    invoke(*args)
    subscribe(tmp_path, entry(kind, source=source.as_uri(), path=path, ref="release"))
    result = CliRunner().invoke(main, [group, "catalog", "add", "reviewer"])
    assert result.exit_code != 0 and "conflict" in result.output.lower()


def test_directory_agent_declared_shape_and_unsupported_target_preflight(tmp_path, sandbox):
    source = repo(tmp_path, {"AGENTS.md": "A complete agent", "MEMORY.md": "Keep me"})
    subscribe(tmp_path, entry(source=source.as_uri(), entryFile="AGENTS.md"))
    result = CliRunner().invoke(main, ["agents", "catalog", "enable", "reviewer", "--scope", "global", "--harnesses", "standard"])
    assert result.exit_code != 0
    assert not (sandbox / ".agent-toolkit/agents-lock.json").exists()
    invoke("agents", "catalog", "enable", "reviewer", "--scope", "global", "--harnesses", "pi")
    assert (sandbox / ".pi/agent/agents/reviewer/MEMORY.md").read_text() == "Keep me"


def test_wrong_agent_shape_never_registers(tmp_path, sandbox):
    source = repo(tmp_path, {"reviewer.md": "flat", "AGENTS.md": "repository instructions"})
    subscribe(tmp_path, entry(source=source.as_uri(), entryFile="AGENTS.md"))
    result = CliRunner().invoke(main, ["agents", "catalog", "add", "reviewer"])
    assert result.exit_code != 0 and "shape" in result.output.lower()
    lock = sandbox / ".agent-toolkit/agents-lock.json"
    assert not lock.exists() or not json.loads(lock.read_text())["skills"]


def test_unmanaged_existing_content_is_preserved(tmp_path, sandbox):
    source = repo(tmp_path, {"COMMAND.md": "source"})
    subscribe(tmp_path, entry("command", source=source.as_uri()))
    target = sandbox / ".agent-toolkit/commands/reviewer"
    target.mkdir(parents=True)
    (target / "COMMAND.md").write_text("mine")
    result = CliRunner().invoke(main, ["commands", "catalog", "add", "reviewer"])
    assert result.exit_code != 0
    assert (target / "COMMAND.md").read_text() == "mine"
    assert not (sandbox / ".agent-toolkit/commands-lock.json").exists()


def test_git_pi_enable_cannot_dispatch_to_native_npm(tmp_path, sandbox, monkeypatch):
    source = repo(tmp_path, {"index.ts": "export default () => {}"})
    subscribe(tmp_path, entry("pi-extension", source=source.as_uri()))
    from agent_toolkit_cli import pi_npm_lifecycle
    monkeypatch.setattr(pi_npm_lifecycle, "npm_source_for", lambda *args, **kwargs: "npm:reviewer@1.2.3")
    monkeypatch.setattr(pi_npm_lifecycle, "install_npm", lambda **kwargs: pytest.fail("Git selection must not install npm"))
    invoke("pi-extensions", "catalog", "enable", "reviewer", "--scope", "global")
    assert (sandbox / ".pi/agent/extensions/reviewer").is_symlink()


def test_npm_requires_explicit_install_and_confirmation(tmp_path, sandbox, monkeypatch):
    subscribe(tmp_path, dict(kind="pi-extension", key="native", description="Native package",
                            sourceType="npm", source="npm:@example/tools@1.2.3"))
    calls = []
    from agent_toolkit_cli import pi_npm_lifecycle
    monkeypatch.setattr(pi_npm_lifecycle, "install_npm", lambda **kwargs: calls.append(kwargs))
    from agent_toolkit_cli import pi_npm
    monkeypatch.setattr(pi_npm, "read_npm_states", lambda **kwargs: {})
    for verb in ("add", "enable"):
        args = ["pi-extensions", "catalog", verb, "native"]
        if verb == "enable":
            args += ["--scope", "global"]
        result = CliRunner().invoke(main, args)
        assert result.exit_code != 0
    args = ["pi-extensions", "catalog", "install", "native", "--scope", "global"]
    assert CliRunner().invoke(main, args).exit_code != 0
    assert calls == []
    invoke(*args, "--yes")
    assert calls[0]["source"] == "npm:@example/tools@1.2.3"
    assert calls[0]["scope"] == "global"
    assert not (sandbox / ".agent-toolkit/pi-extensions-lock.json").exists()
