"""Tests for the MCP adapter base + JSON-family adapter."""
from __future__ import annotations

import json

import pytest

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.mcp_adapters import (
    UnsupportedMcpHarnessError,
    atomic_write_text,
    get_adapter,
)


def test_get_adapter_dispatches_known_harnesses():
    for harness in ("claude-code", "codex", "opencode", "pi"):
        adapter = get_adapter(harness)
        assert adapter.name == harness


def test_get_adapter_unknown_harness_raises():
    with pytest.raises(UnsupportedMcpHarnessError):
        get_adapter("emacs")


def test_atomic_write_text_replaces_in_place(tmp_path):
    target = tmp_path / "config.json"
    target.write_text('{"old": true}')
    atomic_write_text(target, '{"new": true}')
    assert json.loads(target.read_text()) == {"new": True}
    # No temp files left behind
    leftovers = [p for p in tmp_path.iterdir() if p.name != "config.json"]
    assert leftovers == []


def test_atomic_write_text_creates_parent_dirs(tmp_path):
    target = tmp_path / "nested" / "deep" / "config.json"
    atomic_write_text(target, "{}")
    assert target.read_text() == "{}"


def _claude_inner():
    return {"type": "stdio", "command": "npx", "args": ["-y", "ctx7"]}


def test_claude_install_creates_file_with_valid_shape_when_absent(tmp_path):
    """Absent .mcp.json must be created as {"mcpServers": {...}}, NOT skipped."""
    adapter = get_adapter("claude-code")
    project = tmp_path / "proj"
    project.mkdir()
    written = adapter.install(
        "context7", _claude_inner(), scope="project", home=tmp_path, project=project,
    )
    assert written == project / ".mcp.json"
    doc = json.loads(written.read_text())
    assert doc["mcpServers"]["context7"] == _claude_inner()


def test_claude_install_normalises_bare_empty_object(tmp_path):
    """A bare {} (no mcpServers key) is normalised to {"mcpServers": {}} then upserted."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".mcp.json").write_text("{}\n")
    adapter = get_adapter("claude-code")
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    doc = json.loads((project / ".mcp.json").read_text())
    assert doc == {"mcpServers": {"context7": _claude_inner()}}


def test_claude_install_preserves_hand_rolled_entries(tmp_path):
    """Round-trip: a hand-rolled entry is byte-preserved; only our name is added."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"handrolled": {"command": "x"}}}, indent=2) + "\n"
    )
    adapter = get_adapter("claude-code")
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    doc = json.loads((project / ".mcp.json").read_text())
    assert doc["mcpServers"]["handrolled"] == {"command": "x"}
    assert doc["mcpServers"]["context7"] == _claude_inner()


def test_claude_uninstall_removes_only_named_entry(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    adapter = get_adapter("claude-code")
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    doc = json.loads((project / ".mcp.json").read_text())
    doc["mcpServers"]["keepme"] = {"command": "y"}
    (project / ".mcp.json").write_text(json.dumps(doc, indent=2) + "\n")
    adapter.uninstall("context7", scope="project", home=tmp_path, project=project)
    doc2 = json.loads((project / ".mcp.json").read_text())
    assert "context7" not in doc2["mcpServers"]
    assert doc2["mcpServers"]["keepme"] == {"command": "y"}


def test_claude_uninstall_absent_is_noop(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    get_adapter("claude-code").uninstall("context7", scope="project", home=tmp_path, project=project)
    assert not (project / ".mcp.json").exists()


def test_claude_install_is_idempotent(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    adapter = get_adapter("claude-code")
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    first = (project / ".mcp.json").read_text()
    adapter.install("context7", _claude_inner(), scope="project", home=tmp_path, project=project)
    assert (project / ".mcp.json").read_text() == first


def test_claude_user_scope_target_is_home_claude_json(tmp_path):
    adapter = get_adapter("claude-code")
    target = adapter.config_target(scope="global", home=tmp_path, project=None)
    assert target == tmp_path / ".claude.json"


def test_opencode_install_translates_to_native_shape(tmp_path):
    """OpenCode: command:str+args[] → command:[exe,...args]; env → environment."""
    project = tmp_path / "proj"
    project.mkdir()
    adapter = get_adapter("opencode")
    adapter.install(
        "context7",
        {"type": "stdio", "command": "npx", "args": ["-y", "ctx7"], "env": {"K": "${V}"}},
        scope="project", home=tmp_path, project=project,
    )
    doc = json.loads((project / "opencode.json").read_text())
    entry = doc["mcp"]["context7"]
    assert entry["command"] == ["npx", "-y", "ctx7"]
    assert entry["environment"] == {"K": "{env:V}"}
    assert entry["type"] == "local"


def test_pi_user_scope_target_is_pi_agent_mcp_json(tmp_path):
    """Pi user → ~/.pi/agent/mcp.json (corrected 2026-06-13, NOT ~/.config/mcp/mcp.json)."""
    adapter = get_adapter("pi")
    target = adapter.config_target(scope="global", home=tmp_path, project=None)
    assert target == tmp_path / ".pi" / "agent" / "mcp.json"


def test_pi_project_scope_target_is_shared_mcp_json(tmp_path):
    """Pi project → the SHARED .mcp.json (same file as claude-code project), NOT .pi/mcp.json."""
    adapter = get_adapter("pi")
    project = tmp_path / "proj"
    project.mkdir()
    target = adapter.config_target(scope="project", home=tmp_path, project=project)
    assert target == project / ".mcp.json"


def _opencode_install(tmp_path, inner):
    project = tmp_path / "proj"
    project.mkdir()
    get_adapter("opencode").install(
        "context7", inner, scope="project", home=tmp_path, project=project,
    )


def test_opencode_refuses_shell_default_var(tmp_path):
    """env ${V:-x} (shell-default) must raise, never emit a malformed {env:...} ref."""
    with pytest.raises(InstallError):
        _opencode_install(
            tmp_path,
            {"type": "stdio", "command": "npx", "args": ["x"], "env": {"K": "${V:-x}"}},
        )


@pytest.mark.parametrize("bad", ["${V:?e}", "${V:+a}", "${V-d}", "${V:1:2}", "${O${I}}"])
def test_opencode_refuses_other_shell_expansions(tmp_path, bad):
    """Any ${...} that is not a clean bare-variable reference must raise."""
    with pytest.raises(InstallError):
        _opencode_install(
            tmp_path,
            {"type": "stdio", "command": "npx", "args": ["x"], "env": {"K": bad}},
        )


def test_opencode_accepts_plain_var(tmp_path):
    """The clean path still works: ${V} → {env:V}."""
    project = tmp_path / "proj"
    project.mkdir()
    get_adapter("opencode").install(
        "context7",
        {"type": "stdio", "command": "npx", "args": ["x"], "env": {"K": "${V}"}},
        scope="project", home=tmp_path, project=project,
    )
    doc = json.loads((project / "opencode.json").read_text())
    assert doc["mcp"]["context7"]["environment"] == {"K": "{env:V}"}


def test_opencode_refuses_url_source(tmp_path):
    """A url/remote source (no `command`) must raise, never write command:[]."""
    with pytest.raises(InstallError):
        _opencode_install(
            tmp_path,
            {"type": "http", "url": "https://example.com/mcp"},
        )
