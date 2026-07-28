"""Tests for the authoritative global MCP library manifest."""
from __future__ import annotations

import json

import pytest

from agent_toolkit_cli.mcp_library import McpAsset
from agent_toolkit_cli.mcp_manifest import (
    McpManifestEntry,
    UnsafeMcpSpecError,
    assert_safe_entry,
    entry_from_materialisation,
    entry_to_inner_config,
    entry_to_metadata,
    manifest_path,
    read_manifest,
    write_manifest,
)


def test_manifest_round_trip_is_sorted_and_newline_terminated(tmp_path):
    entries = {
        "zeta": McpManifestEntry(
            "zeta", "url", "http", "https://z/sse", None, (), (), None, None
        ),
        "alpha": McpManifestEntry(
            "alpha",
            "npx",
            "stdio",
            "alpha",
            "npx",
            ("-y", "alpha@1.0.0"),
            ("API_TOKEN",),
            "x",
            "1.0.0",
        ),
    }

    path = manifest_path(tmp_path)
    write_manifest(path, entries)

    assert list(json.loads(path.read_text())["mcps"]) == ["alpha", "zeta"]
    assert path.read_text().endswith("\n")
    assert read_manifest(path) == entries


@pytest.mark.parametrize(
    "body",
    [
        '{"version": 2, "mcps": {}}',
        '{"version": 1, "mcps": {"a": {"slug": "other"}}}',
        "{not json}",
    ],
)
def test_read_manifest_fails_loud_on_invalid_envelope(tmp_path, body):
    path = tmp_path / "mcps-library.json"
    path.write_text(body)

    with pytest.raises((ValueError, json.JSONDecodeError)):
        read_manifest(path)


def test_read_manifest_rejects_unknown_and_duplicate_fields(tmp_path):
    path = tmp_path / "mcps-library.json"
    valid = {
        "slug": "demo",
        "install_method": "url",
        "transport": "http",
        "source": "https://host/sse",
        "command": None,
        "args": [],
        "env": [],
        "description": None,
        "resolved_version": None,
    }
    path.write_text(json.dumps({"version": 1, "mcps": {"demo": {**valid, "extra": 1}}}))
    with pytest.raises(ValueError):
        read_manifest(path)

    path.write_text('{"version":1,"version":1,"mcps":{}}')
    with pytest.raises(ValueError):
        read_manifest(path)


def test_missing_manifest_reads_as_empty(tmp_path):
    assert read_manifest(tmp_path / "missing.json") == {}


def test_url_entry_materialises_from_source_only():
    entry = McpManifestEntry(
        "remote", "url", "http", "https://host/sse", None, (), (), None, None
    )

    assert entry_to_inner_config(entry) == {
        "type": "http",
        "url": "https://host/sse",
    }
    assert entry_to_metadata(entry) == {
        "name": "remote",
        "install_method": "url",
        "transport": "http",
    }


@pytest.mark.parametrize(
    ("entry", "literal"),
    [
        (
            McpManifestEntry(
                "bad-url",
                "url",
                "http",
                "https://u:pw@host/sse",
                None,
                (),
                (),
                None,
                None,
            ),
            "pw",
        ),
        (
            McpManifestEntry(
                "bad-arg",
                "local",
                "stdio",
                "/srv/mcp",
                "python",
                ("server.py", "--token=real-secret"),
                (),
                None,
                None,
            ),
            "real-secret",
        ),
        (
            McpManifestEntry(
                "bad-provider-token",
                "local",
                "stdio",
                "/srv/mcp",
                "python",
                ("server.py", "sk-proj-abcdefghijklmnopqrstuvwxyz"),
                (),
                None,
                None,
            ),
            "sk-proj-abcdefghijklmnopqrstuvwxyz",
        ),
        (
            McpManifestEntry(
                "bad-command",
                "local",
                "stdio",
                "/srv/mcp",
                "python --token=command-secret",
                (),
                (),
                None,
                None,
            ),
            "command-secret",
        ),
        (
            McpManifestEntry(
                "bad-query",
                "url",
                "http",
                "https://host/sse?key=query-secret",
                None,
                (),
                (),
                None,
                None,
            ),
            "query-secret",
        ),
    ],
)
def test_unsafe_entry_error_redacts_literal(entry, literal):
    with pytest.raises(UnsafeMcpSpecError) as raised:
        assert_safe_entry(entry)

    assert literal not in str(raised.value)
    assert "redacted" in str(raised.value)


@pytest.mark.parametrize(
    "reference",
    ["$API_TOKEN", "${API_TOKEN}"],
)
def test_secret_named_option_allows_environment_reference(reference):
    entry = McpManifestEntry(
        "safe",
        "local",
        "stdio",
        "/srv/mcp",
        "python",
        ("server.py", f"--token={reference}"),
        ("API_TOKEN",),
        None,
        None,
    )

    assert_safe_entry(entry)


@pytest.mark.parametrize(
    "entry",
    [
        McpManifestEntry(
            "uv",
            "uvx",
            "stdio",
            "uv-server",
            "uvx",
            ("uv-server==1.0.0",),
            (),
            None,
            "1.0.0",
        ),
        McpManifestEntry(
            "docker",
            "docker",
            "stdio",
            "ghcr.io/org/server:latest",
            "docker",
            ("run", "--rm", "-i", "ghcr.io/org/server:latest"),
            (),
            None,
            "latest",
        ),
        McpManifestEntry(
            "local",
            "local",
            "stdio",
            "/srv/server",
            "python",
            ("server.py",),
            ("API_TOKEN",),
            None,
            "abc123",
        ),
    ],
)
def test_method_records_materialise_without_losing_authoring_fields(entry):
    inner = entry_to_inner_config(entry)
    metadata = entry_to_metadata(entry)

    assert entry_from_materialisation(McpAsset(entry.slug, inner, metadata)) == entry


def test_untagged_docker_materialisation_normalises_effective_latest_tag():
    asset = McpAsset(
        "docker",
        {
            "type": "stdio",
            "command": "docker",
            "args": ["run", "--rm", "-i", "localhost:5000/org/server"],
        },
        {"name": "docker", "install_method": "docker", "transport": "stdio"},
    )

    entry = entry_from_materialisation(asset)

    assert entry.source == "localhost:5000/org/server:latest"
    assert entry.args[-1] == "localhost:5000/org/server:latest"
    assert entry.resolved_version == "latest"


def test_npx_scoped_package_round_trips_from_materialisation():
    entry = McpManifestEntry(
        "context7",
        "npx",
        "stdio",
        "@upstash/context7-mcp",
        "npx",
        ("-y", "@upstash/context7-mcp@1.2.3"),
        (),
        None,
        "1.2.3",
    )

    assert entry_from_materialisation(
        McpAsset(
            entry.slug,
            entry_to_inner_config(entry),
            entry_to_metadata(entry),
        )
    ) == entry


def test_materialisation_with_config_env_map_is_not_lossless():
    asset = McpAsset(
        "legacy",
        {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "pkg@1.0.0"],
            "env": {"API_TOKEN": "$API_TOKEN"},
        },
        {
            "name": "legacy",
            "install_method": "npx",
            "transport": "stdio",
            "resolved_version": "1.0.0",
        },
    )

    with pytest.raises(ValueError, match="env"):
        entry_from_materialisation(asset)


def test_materialisation_rejects_unknown_shape_instead_of_guessing():
    asset = McpAsset(
        "remote",
        {"type": "http", "url": "https://host/sse", "headers": {}},
        {"name": "remote", "install_method": "url", "transport": "http"},
    )

    with pytest.raises(ValueError, match="cannot be reconstructed"):
        entry_from_materialisation(asset)


def test_materialisation_requires_all_identity_metadata():
    asset = McpAsset(
        "remote",
        {"type": "http", "url": "https://host/sse"},
        {"name": "remote", "description": "incomplete"},
    )

    with pytest.raises(ValueError, match="cannot be reconstructed"):
        entry_from_materialisation(asset)
