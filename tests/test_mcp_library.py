"""Tests for src/agent_toolkit_cli/mcp_library.py — library discovery + parse."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.mcp_library import (
    McpAsset,
    library_root,
    list_library,
    load_mcp_asset,
)


def test_library_root_derives_from_home(tmp_path):
    assert library_root(tmp_path) == tmp_path / ".agent-toolkit" / "mcps"


def _write_library_entry(
    library: Path, slug: str, *, inner: str, sidecar: str
) -> None:
    mcp_dir = library / slug
    mcp_dir.mkdir(parents=True, exist_ok=True)
    (mcp_dir / "config.json").write_text(inner)
    (mcp_dir / "README.md").write_text(f"# {slug}\n")
    (library / f"{slug}.toolkit.yaml").write_text(sidecar)


def test_load_mcp_asset_reads_inner_and_sidecar(tmp_path):
    _write_library_entry(
        tmp_path,
        "context7",
        inner='{"type": "stdio", "command": "npx", "args": ["-y", "ctx7"]}\n',
        sidecar=(
            "name: context7\n"
            "description: Up-to-date docs MCP.\n"
            "transport: stdio\n"
            "install_method: npx\n"
            "env:\n"
            "  - DEFAULT_MINIMUM_TOKENS\n"
        ),
    )
    asset = load_mcp_asset(tmp_path, "context7")
    assert isinstance(asset, McpAsset)
    assert asset.slug == "context7"
    assert asset.inner_config["command"] == "npx"
    assert asset.inner_config["args"] == ["-y", "ctx7"]
    assert asset.transport == "stdio"
    assert asset.install_method == "npx"
    assert asset.env == ["DEFAULT_MINIMUM_TOKENS"]


def test_load_mcp_asset_missing_slug_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_mcp_asset(tmp_path, "does-not-exist")


def test_list_library_returns_slugs_sorted(tmp_path):
    for slug in ("zeta", "alpha"):
        _write_library_entry(
            tmp_path, slug,
            inner='{"type":"stdio","command":"npx"}\n',
            sidecar=f"name: {slug}\ndescription: x.\ntransport: stdio\ninstall_method: npx\n",
        )
    assert list_library(tmp_path) == ["alpha", "zeta"]


def test_load_mcp_asset_without_sidecar_uses_defaults(tmp_path):
    mcp_dir = tmp_path / "orphan"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    asset = load_mcp_asset(tmp_path, "orphan")
    assert asset.slug == "orphan"
    assert asset.metadata == {}
    assert asset.transport is None
