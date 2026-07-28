"""Tests for src/agent_toolkit_cli/mcp_library.py — library discovery + parse."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from agent_toolkit_cli import mcp_library
from agent_toolkit_cli.mcp_library import (
    McpAsset,
    library_root,
    list_library,
    load_mcp_asset,
    materialize_entry,
    scan_entry_files,
)
from agent_toolkit_cli.mcp_manifest import McpManifestEntry


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


def test_scan_entry_files_includes_config_only_and_sidecar_only(tmp_path):
    (tmp_path / "config-only").mkdir()
    config_path = tmp_path / "config-only" / "config.json"
    config_path.write_text("{}")
    sidecar_path = tmp_path / "sidecar-only.toolkit.yaml"
    sidecar_path.write_text("name: sidecar-only\n")

    scanned = scan_entry_files(tmp_path)

    assert scanned["config-only"] == (config_path, None)
    assert scanned["sidecar-only"] == (None, sidecar_path)


def test_materialize_entry_writes_config_and_sidecar_from_manifest(tmp_path):
    entry = McpManifestEntry(
        "demo",
        "npx",
        "stdio",
        "pkg",
        "npx",
        ("-y", "pkg@1.0.0"),
        ("API_TOKEN",),
        "Demo",
        "1.0.0",
    )

    entry_dir = materialize_entry(tmp_path, entry, overwrite=False)

    assert entry_dir == tmp_path / "demo"
    assert json.loads((entry_dir / "config.json").read_text())["args"] == [
        "-y",
        "pkg@1.0.0",
    ]
    metadata = yaml.safe_load((tmp_path / "demo.toolkit.yaml").read_text())
    assert metadata["env"] == ["API_TOKEN"]
    assert (entry_dir / "README.md").read_text() == "# demo\n"


def test_materialize_entry_refuses_either_existing_half(tmp_path):
    entry = McpManifestEntry(
        "demo",
        "url",
        "http",
        "https://host/sse",
        None,
        (),
        (),
        None,
        None,
    )
    (tmp_path / "demo.toolkit.yaml").write_text("name: demo\n")

    with pytest.raises(FileExistsError):
        materialize_entry(tmp_path, entry, overwrite=False)


def test_materialize_entry_leaves_config_only_when_sidecar_write_fails(
    tmp_path, monkeypatch
):
    real_write = mcp_library.atomic_write_text

    def fail_sidecar(path, content):
        if path.name.endswith(".toolkit.yaml"):
            raise OSError("simulated sidecar failure")
        real_write(path, content)

    monkeypatch.setattr(mcp_library, "atomic_write_text", fail_sidecar)
    entry = McpManifestEntry(
        "demo",
        "npx",
        "stdio",
        "pkg",
        "npx",
        ("-y", "pkg@1.0.0"),
        (),
        None,
        "1.0.0",
    )

    with pytest.raises(OSError, match="simulated sidecar failure"):
        materialize_entry(tmp_path, entry, overwrite=False)

    assert (tmp_path / "demo" / "config.json").is_file()
    assert not (tmp_path / "demo.toolkit.yaml").exists()
