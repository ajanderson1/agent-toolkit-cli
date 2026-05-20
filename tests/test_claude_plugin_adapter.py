"""Unit tests for ClaudePluginAdapter.

This module starts with Task 4.1's skeleton tests (path computation,
list_installed empty case, can_install no-op). The full round-trip
behaviour tests — first-install, sibling preservation, marketplace
name-collision, version pinning, shared-marketplace revert — land in
Tasks 4.2 through 4.6 of plan 2026-05-20-claude-plugin-asset-kind.md.
"""

from __future__ import annotations

from pathlib import Path


def test_config_target_user_scope(monkeypatch):
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    monkeypatch.setenv("HOME", "/tmp/fake-home")
    adapter = ClaudePluginAdapter()
    assert adapter.config_target("user", Path("/irrelevant")) == \
        Path("/tmp/fake-home/.claude/plugins/installed_plugins.json")


def test_config_target_project_scope_returns_none(monkeypatch):
    """Project scope is out of scope for v1."""
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    adapter = ClaudePluginAdapter()
    assert adapter.config_target("project", Path("/tmp/proj")) is None


def test_marketplaces_target_user_scope(monkeypatch):
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    monkeypatch.setenv("HOME", "/tmp/fake-home")
    adapter = ClaudePluginAdapter()
    assert adapter.marketplaces_target("user", Path("/irrelevant")) == \
        Path("/tmp/fake-home/.claude/plugins/known_marketplaces.json")


def test_can_install_no_preflight_refusal():
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry
    entry = PluginEntry(
        name="x", marketplace="m",
        marketplace_source={"source": "git", "url": "https://example.com/m.git"},
        plugin="x", version="latest",
    )
    ClaudePluginAdapter().can_install(entry)  # must not raise


def test_list_installed_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    assert ClaudePluginAdapter().list_installed("user", tmp_path) == set()
