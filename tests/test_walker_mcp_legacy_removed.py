"""Regression: MCP README-frontmatter is no longer parsed for toolkit metadata."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.walker import discover_assets


def test_mcp_with_only_readme_frontmatter_is_not_discovered(tmp_path: Path) -> None:
    """After PR 3, a stale README-with-frontmatter MCP shows up as orphan, not asset."""
    mcp_dir = tmp_path / "mcps" / "ghost"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"x"}')
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: ghost\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n    command: x\n"
        "---\n# ghost\n"
    )
    assets = discover_assets(tmp_path)
    slugs = {a.slug for a in assets if a.kind == "mcp"}
    assert "ghost" not in slugs


def test_mcp_with_sidecar_is_discovered(tmp_path: Path) -> None:
    mcp_dir = tmp_path / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"x"}')
    (mcp_dir / "README.md").write_text("# context7\n\nNo frontmatter, just docs.\n")
    (tmp_path / "mcps" / "context7.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n    command: x\n"
    )
    assets = discover_assets(tmp_path)
    slugs = {a.slug for a in assets if a.kind == "mcp"}
    assert "context7" in slugs
