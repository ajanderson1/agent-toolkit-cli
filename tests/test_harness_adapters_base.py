"""Tests for harness_adapters.base dataclasses."""
from __future__ import annotations


def test_plugin_entry_carries_source_fields():
    from agent_toolkit_cli.harness_adapters.base import PluginEntry
    entry = PluginEntry(
        name="superpowers",
        marketplace="claude-plugins-official",
        marketplace_source={"source": "git", "url": "https://x.example/y.git"},
        plugin="superpowers",
        version="latest",
    )
    assert entry.name == "superpowers"
    assert entry.marketplace == "claude-plugins-official"
    assert entry.marketplace_source["source"] == "git"
    assert entry.plugin == "superpowers"
    assert entry.version == "latest"


def test_plugin_entry_is_frozen():
    """Adapter entries are immutable, consistent with McpEntry."""
    from agent_toolkit_cli.harness_adapters.base import PluginEntry
    import dataclasses
    import pytest
    entry = PluginEntry(
        name="x", marketplace="m",
        marketplace_source={"source": "git", "url": "https://x.example/m.git"},
        plugin="x", version="latest",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.name = "y"  # type: ignore[misc]
