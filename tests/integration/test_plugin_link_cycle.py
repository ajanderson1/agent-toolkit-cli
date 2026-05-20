"""Integration: link → list → diff → unlink → list for plugin:superpowers.

Tests the full CLI dispatch path through ClaudePluginAdapter.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def toolkit_repo(tmp_path):
    """A minimal toolkit repo containing the superpowers plugin sidecar."""
    root = tmp_path / "toolkit"
    plugins = root / "plugins"
    plugins.mkdir(parents=True)
    fixture = (
        Path(__file__).parent.parent
        / "fixtures"
        / "plugin_sidecars"
        / "superpowers.toolkit.yaml"
    )
    (plugins / "superpowers.toolkit.yaml").write_text(fixture.read_text())
    (root / ".agent-toolkit-source").touch()
    schemas = root / "schemas"
    schemas.mkdir()
    (schemas / "asset-frontmatter.v1alpha2.json").write_text("{}")
    return root


def test_link_writes_to_both_json_files(fake_home, toolkit_repo):
    """`link user claude plugin:superpowers` writes both Claude JSON files."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main as cli

    runner = CliRunner()

    # Pre-existing sibling marketplace must survive.
    (fake_home / ".claude" / "plugins").mkdir(parents=True)
    (fake_home / ".claude" / "plugins" / "known_marketplaces.json").write_text(
        json.dumps(
            {
                "hand-rolled": {
                    "source": {"source": "directory", "path": "/some/path"},
                },
            },
            indent=2,
        )
        + "\n"
    )

    result = runner.invoke(
        cli,
        [
            "--toolkit-repo",
            str(toolkit_repo),
            "link",
            "user",
            "claude",
            "plugin:superpowers",
        ],
    )
    assert result.exit_code == 0, result.output

    installed = json.loads(
        (fake_home / ".claude/plugins/installed_plugins.json").read_text()
    )
    assert "superpowers@claude-plugins-official" in installed["plugins"]

    markets = json.loads(
        (fake_home / ".claude/plugins/known_marketplaces.json").read_text()
    )
    assert "claude-plugins-official" in markets
    assert "hand-rolled" in markets, "pre-existing sibling marketplace must survive"


def test_unlink_removes_entry_and_orphan_marketplace(fake_home, toolkit_repo):
    """Unlink removes the plugin entry AND its orphan marketplace; siblings survive."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main as cli

    runner = CliRunner()

    # Pre-seed sibling
    (fake_home / ".claude" / "plugins").mkdir(parents=True)
    (fake_home / ".claude" / "plugins" / "known_marketplaces.json").write_text(
        json.dumps(
            {
                "hand-rolled": {
                    "source": {"source": "directory", "path": "/some/path"},
                },
            },
            indent=2,
        )
        + "\n"
    )

    # Link, then unlink.
    runner.invoke(
        cli,
        [
            "--toolkit-repo",
            str(toolkit_repo),
            "link",
            "user",
            "claude",
            "plugin:superpowers",
        ],
    )
    result = runner.invoke(
        cli,
        [
            "--toolkit-repo",
            str(toolkit_repo),
            "unlink",
            "user",
            "claude",
            "plugin:superpowers",
        ],
    )
    assert result.exit_code == 0, result.output

    installed = json.loads(
        (fake_home / ".claude/plugins/installed_plugins.json").read_text()
    )
    assert "superpowers@claude-plugins-official" not in installed["plugins"]

    markets = json.loads(
        (fake_home / ".claude/plugins/known_marketplaces.json").read_text()
    )
    assert (
        "claude-plugins-official" not in markets
    ), "orphan marketplace must be dropped"
    assert "hand-rolled" in markets, "sibling marketplace must be preserved"
