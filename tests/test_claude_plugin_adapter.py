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


def test_diff_creates_both_files_on_first_install(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry
    import json

    entry = PluginEntry(
        name="superpowers",
        marketplace="claude-plugins-official",
        marketplace_source={"source": "git", "url": "https://github.com/anthropics/claude-plugins-official.git"},
        plugin="superpowers",
        version="latest",
    )
    actions = ClaudePluginAdapter().diff("user", tmp_path, [entry])
    paths = sorted(a.path.name for a in actions)
    assert paths == ["installed_plugins.json", "known_marketplaces.json"]
    assert all(a.op == "create" for a in actions)

    for action in actions:
        action.path.parent.mkdir(parents=True, exist_ok=True)
        action.path.write_bytes(action.contents)

    doc = json.loads((tmp_path / ".claude/plugins/installed_plugins.json").read_text())
    assert doc["version"] == 2
    assert "superpowers@claude-plugins-official" in doc["plugins"]
    user_entries = [e for e in doc["plugins"]["superpowers@claude-plugins-official"]
                    if e.get("scope") == "user"]
    assert len(user_entries) == 1
    assert user_entries[0]["version"] == "latest"
    for forbidden in ("installedAt", "gitCommitSha", "lastUpdated", "installPath"):
        assert forbidden not in user_entries[0]


def test_diff_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry

    entry = PluginEntry(
        name="superpowers",
        marketplace="claude-plugins-official",
        marketplace_source={"source": "git", "url": "https://github.com/anthropics/claude-plugins-official.git"},
        plugin="superpowers",
        version="latest",
    )
    adapter = ClaudePluginAdapter()
    actions = adapter.diff("user", tmp_path, [entry])
    for action in actions:
        action.path.parent.mkdir(parents=True, exist_ok=True)
        action.path.write_bytes(action.contents)
    actions2 = adapter.diff("user", tmp_path, [entry],
                            previously_allowed={"superpowers@claude-plugins-official"})
    assert actions2 == [], "second pass should produce no WriteActions"


def test_diff_preserves_unrelated_sibling_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import json
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry

    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    pre_installed = {
        "version": 2,
        "plugins": {
            "hand-rolled@private": [
                {"scope": "user", "version": "1.2.3",
                 "installedAt": "2026-04-01T00:00:00Z",
                 "lastUpdated": "2026-04-01T00:00:00Z",
                 "installPath": "/some/path"}
            ]
        },
    }
    (plugins_dir / "installed_plugins.json").write_text(
        json.dumps(pre_installed, indent=2) + "\n"
    )
    pre_markets = {
        "private": {
            "source": {"source": "directory", "path": "/some/dir"},
            "installLocation": "/some/install",
            "lastUpdated": "2026-04-01T00:00:00Z",
        }
    }
    (plugins_dir / "known_marketplaces.json").write_text(
        json.dumps(pre_markets, indent=2) + "\n"
    )

    entry = PluginEntry(
        name="superpowers", marketplace="claude-plugins-official",
        marketplace_source={"source": "git", "url": "https://x.example/y.git"},
        plugin="superpowers", version="latest",
    )
    actions = ClaudePluginAdapter().diff("user", tmp_path, [entry])
    for action in actions:
        action.path.write_bytes(action.contents)

    after_installed = json.loads((plugins_dir / "installed_plugins.json").read_text())
    assert "hand-rolled@private" in after_installed["plugins"]
    assert after_installed["plugins"]["hand-rolled@private"][0]["installedAt"] == "2026-04-01T00:00:00Z"
    assert after_installed["plugins"]["hand-rolled@private"][0]["installPath"] == "/some/path"

    after_markets = json.loads((plugins_dir / "known_marketplaces.json").read_text())
    assert "private" in after_markets
    assert after_markets["private"]["installLocation"] == "/some/install"

    assert "superpowers@claude-plugins-official" in after_installed["plugins"]
    assert "claude-plugins-official" in after_markets


def test_diff_refuses_marketplace_name_collision(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import json
    import pytest
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry, CannotInstall

    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "known_marketplaces.json").write_text(json.dumps({
        "claude-plugins-official": {
            "source": {"source": "git", "url": "https://NOT-the-right-url/x.git"},
        }
    }, indent=2) + "\n")

    entry = PluginEntry(
        name="superpowers", marketplace="claude-plugins-official",
        marketplace_source={"source": "git", "url": "https://github.com/anthropics/claude-plugins-official.git"},
        plugin="superpowers", version="latest",
    )
    with pytest.raises(CannotInstall, match="already recorded with a different source"):
        ClaudePluginAdapter().diff("user", tmp_path, [entry])


def test_pinned_version_forces_rewrite(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import json
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry

    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "installed_plugins.json").write_text(json.dumps({
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [
                {"scope": "user", "version": "5.1.0",
                 "installedAt": "x", "lastUpdated": "y", "installPath": "/p"}
            ]
        }
    }, indent=2) + "\n")
    (plugins_dir / "known_marketplaces.json").write_text(json.dumps({
        "claude-plugins-official": {
            "source": {"source": "git", "url": "https://github.com/anthropics/claude-plugins-official.git"},
        }
    }, indent=2) + "\n")

    entry = PluginEntry(
        name="superpowers", marketplace="claude-plugins-official",
        marketplace_source={"source": "git", "url": "https://github.com/anthropics/claude-plugins-official.git"},
        plugin="superpowers", version="6.0.0",
    )
    actions = ClaudePluginAdapter().diff(
        "user", tmp_path, [entry],
        previously_allowed={"superpowers@claude-plugins-official"},
    )
    assert len(actions) == 1
    assert actions[0].path.name == "installed_plugins.json"
    assert actions[0].op == "update"

    actions[0].path.write_bytes(actions[0].contents)
    after = json.loads((plugins_dir / "installed_plugins.json").read_text())
    e = after["plugins"]["superpowers@claude-plugins-official"][0]
    assert e["version"] == "6.0.0"
    assert e["installedAt"] == "x"
    assert e["lastUpdated"] == "y"
    assert e["installPath"] == "/p"


def test_latest_leaves_recorded_version_alone(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import json
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry

    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "installed_plugins.json").write_text(json.dumps({
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [
                {"scope": "user", "version": "5.1.0"}
            ]
        }
    }, indent=2) + "\n")
    (plugins_dir / "known_marketplaces.json").write_text(json.dumps({
        "claude-plugins-official": {"source": {"source": "git", "url": "https://x/y.git"}}
    }, indent=2) + "\n")

    entry = PluginEntry(
        name="superpowers", marketplace="claude-plugins-official",
        marketplace_source={"source": "git", "url": "https://x/y.git"},
        plugin="superpowers", version="latest",
    )
    actions = ClaudePluginAdapter().diff(
        "user", tmp_path, [entry],
        previously_allowed={"superpowers@claude-plugins-official"},
    )
    assert actions == [], "no-op expected: 'latest' must not touch a pinned recorded version"


def test_revert_drops_marketplace_when_unused(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import json
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter

    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "installed_plugins.json").write_text(json.dumps({
        "version": 2,
        "plugins": {"superpowers@cpo": [{"scope": "user", "version": "latest"}]}
    }, indent=2) + "\n")
    (plugins_dir / "known_marketplaces.json").write_text(json.dumps({
        "cpo": {"source": {"source": "git", "url": "https://x/y.git"}}
    }, indent=2) + "\n")

    actions = ClaudePluginAdapter().diff(
        "user", tmp_path, [], previously_allowed={"superpowers@cpo"},
    )
    for action in actions:
        if action.contents is not None:
            action.path.write_bytes(action.contents)
        else:
            action.path.unlink(missing_ok=True)

    installed = json.loads((plugins_dir / "installed_plugins.json").read_text())
    markets = json.loads((plugins_dir / "known_marketplaces.json").read_text())
    assert "superpowers@cpo" not in installed["plugins"]
    assert "cpo" not in markets


def test_revert_keeps_marketplace_when_shared(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import json
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry

    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "installed_plugins.json").write_text(json.dumps({
        "version": 2,
        "plugins": {
            "superpowers@cpo": [{"scope": "user", "version": "latest"}],
            "compound@cpo":    [{"scope": "user", "version": "latest"}],
        }
    }, indent=2) + "\n")
    (plugins_dir / "known_marketplaces.json").write_text(json.dumps({
        "cpo": {"source": {"source": "git", "url": "https://x/y.git"}}
    }, indent=2) + "\n")

    keep = PluginEntry(
        name="compound", marketplace="cpo",
        marketplace_source={"source": "git", "url": "https://x/y.git"},
        plugin="compound", version="latest",
    )
    actions = ClaudePluginAdapter().diff(
        "user", tmp_path, [keep],
        previously_allowed={"superpowers@cpo", "compound@cpo"},
    )
    for action in actions:
        action.path.write_bytes(action.contents)

    installed = json.loads((plugins_dir / "installed_plugins.json").read_text())
    markets = json.loads((plugins_dir / "known_marketplaces.json").read_text())
    assert "superpowers@cpo" not in installed["plugins"]
    assert "compound@cpo" in installed["plugins"]
    assert "cpo" in markets


def test_get_adapter_returns_claude_plugin_adapter():
    """The dispatcher returns the real ClaudePluginAdapter, not UnimplementedAdapter."""
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    adapter = get_adapter("claude", "plugin")
    assert isinstance(adapter, ClaudePluginAdapter)
