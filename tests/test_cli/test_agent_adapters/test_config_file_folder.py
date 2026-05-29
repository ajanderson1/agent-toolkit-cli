"""config_file_folder mechanism: 3 cells with registry mutation.

  - aider-desk: per-slug config.json + order.json sort.
  - dexto: per-slug yml subdir; parent-allowedAgents edit is OUT OF SCOPE for PR2.
  - firebender: atomic firebender.json mutation; callable: true in markdown.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def fake_content(tmp_path):
    content = tmp_path / "canonical" / "test-agent.md"
    content.parent.mkdir(parents=True, exist_ok=True)
    content.write_text(
        "---\nname: test-agent\ndescription: test\n---\n\nBody text.\n"
    )
    return content


# ── aider-desk ───────────────────────────────────────────────────────────

def test_aider_desk_install_writes_per_slug_subdir(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("aider-desk")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".aider-desk" / "agents" / "test-agent" / "config.json"
    assert result.exists()
    body = json.loads(result.read_text())
    assert body["subagent"]["enabled"] is True


def test_aider_desk_uninstall_removes_subdir(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("aider-desk")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    subdir = tmp_path / ".aider-desk" / "agents" / "test-agent"
    assert subdir.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not subdir.exists()


# ── dexto ────────────────────────────────────────────────────────────────

def test_dexto_install_writes_yml_in_per_agent_subdir(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("dexto")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".dexto" / "agents" / "test-agent" / "test-agent.yml"
    assert result.exists()


def test_dexto_project_scope_raises_unsupported(tmp_path, fake_content):
    """Dexto has no project-scope convention per spec addendum."""
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("dexto")
    project = tmp_path / "proj"
    project.mkdir()
    with pytest.raises(ValueError, match="dexto"):
        adapter.install("test-agent", fake_content, scope="project", project=project)


# ── firebender ───────────────────────────────────────────────────────────

def test_firebender_install_writes_md_with_callable_true(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    result = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert result == tmp_path / ".firebender" / "agents" / "test-agent.md"
    text = result.read_text()
    assert "callable: true" in text


def test_firebender_install_appends_to_firebender_json(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    fb_json = tmp_path / ".firebender" / "firebender.json"
    assert fb_json.exists()
    body = json.loads(fb_json.read_text())
    assert "agents" in body
    assert any("test-agent.md" in p for p in body["agents"])


def test_firebender_preserves_unrelated_json_keys(tmp_path, fake_content):
    """firebender.json may have other keys (mcp_servers, etc.); preserve them."""
    fb_dir = tmp_path / ".firebender"
    fb_dir.mkdir()
    fb_json = fb_dir / "firebender.json"
    fb_json.write_text(json.dumps({
        "agents": ["existing-agent.md"],
        "mcp_servers": {"foo": {"command": "bar"}},
    }, indent=2))

    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)

    body = json.loads(fb_json.read_text())
    # Both agents present
    assert any("existing-agent.md" in p for p in body["agents"])
    assert any("test-agent.md" in p for p in body["agents"])
    # Unrelated keys preserved
    assert body["mcp_servers"] == {"foo": {"command": "bar"}}


def test_firebender_uninstall_removes_from_json_and_file(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    md = tmp_path / ".firebender" / "agents" / "test-agent.md"
    assert md.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not md.exists()
    body = json.loads((tmp_path / ".firebender" / "firebender.json").read_text())
    assert not any("test-agent.md" in p for p in body["agents"])


# ── Fail-loud regression tests (per Task 8 lessons) ──

def test_adapter_for_unknown_harness_raises():
    from agent_toolkit_cli.agent_adapters import config_file_folder
    from agent_toolkit_cli.skill_agents import UnknownAgentError
    with pytest.raises(UnknownAgentError):
        config_file_folder.adapter_for("nonexistent-harness-xyz")


def test_install_with_invalid_scope_raises(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("aider-desk")
    with pytest.raises(ValueError, match="global.*project"):
        adapter.install("test", fake_content, scope="globall", home=tmp_path)
