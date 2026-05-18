"""Tests for the `pi-extension` asset kind end-to-end.

Covers walker discovery, allow-list round-trip, ingest research routing,
kind-aware harness reading, the `new` scaffold, and link/unlink projection.
"""
from __future__ import annotations

import os
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli._allowlist import (
    SECTIONS,
    kind_to_section,
    read_allowlist,
    section_to_kind,
)
from agent_toolkit_cli.cli import main
from agent_toolkit_cli.commands._link_lib import _asset_harnesses
from agent_toolkit_cli.ingest.research import infer_from_snapshot
from agent_toolkit_cli.walker import discover_assets, load_asset_record


# ---------------------------------------------------------------------------
# Walker discovery
# ---------------------------------------------------------------------------


def test_walker_discovers_pi_extension(env, seed_pi_extension):
    toolkit = env["toolkit_root"]
    seed_pi_extension(toolkit, "status-bar", ["pi"])

    assets = [a for a in discover_assets(toolkit) if a.kind == "pi-extension"]
    assert len(assets) == 1
    asset = assets[0]
    assert asset.slug == "status-bar"
    assert asset.path.name == "extension.meta.yaml"


def test_walker_loads_pi_extension_metadata_from_yaml(env, seed_pi_extension):
    toolkit = env["toolkit_root"]
    seed_pi_extension(toolkit, "status-bar", ["pi"])

    asset = next(a for a in discover_assets(toolkit) if a.kind == "pi-extension")
    record = load_asset_record(asset)
    assert record.metadata["metadata"]["name"] == "status-bar"
    assert record.metadata["spec"]["harnesses"] == ["pi"]


# ---------------------------------------------------------------------------
# Allow-list section routing
# ---------------------------------------------------------------------------


def test_allowlist_section_includes_pi_extensions():
    assert "pi_extensions" in SECTIONS
    assert kind_to_section("pi-extension") == "pi_extensions"
    assert section_to_kind("pi_extensions") == "pi-extension"


def test_allowlist_round_trips_pi_extensions_section(tmp_path):
    f = tmp_path / "a.yaml"
    f.write_text("pi_extensions:\n  - status-bar\n  - ceo-board\n")
    result = read_allowlist(f)
    assert result["pi_extensions"] == ["status-bar", "ceo-board"]


# ---------------------------------------------------------------------------
# Kind-aware harness loader
# ---------------------------------------------------------------------------


def test_asset_harnesses_reads_pi_extension_yaml(env, seed_pi_extension):
    toolkit = env["toolkit_root"]
    ext_dir = seed_pi_extension(toolkit, "status-bar", ["pi"])
    manifest = ext_dir / "extension.meta.yaml"
    assert _asset_harnesses(manifest, "pi-extension") == ["pi"]


def test_asset_harnesses_legacy_call_misses_pure_yaml(env, seed_pi_extension):
    """Without kind=, the loader falls through to markdown-frontmatter parsing.

    Pin this so a future caller migrating from the legacy signature gets [], not
    a silent wrong answer from accidentally parsing the YAML body as a doc.
    """
    toolkit = env["toolkit_root"]
    ext_dir = seed_pi_extension(toolkit, "status-bar", ["pi"])
    manifest = ext_dir / "extension.meta.yaml"
    assert _asset_harnesses(manifest) == []


# ---------------------------------------------------------------------------
# Ingest routing
# ---------------------------------------------------------------------------


def test_research_routes_extension_meta_yaml_to_pi_extension(tmp_path):
    (tmp_path / "extension.meta.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: thing\n"
    )
    proposal = infer_from_snapshot(
        snapshot_dir=tmp_path, slug="thing", upstream=None,
    )
    assert proposal.kind == "pi-extension"
    assert proposal.harnesses == ["pi"]
    assert proposal.target_path == "extensions/thing/extension.meta.yaml"


def test_research_routes_pi_extension_keyword_to_pi_extension(tmp_path):
    (tmp_path / "package.json").write_text('{"keywords": ["pi-extension"]}')
    proposal = infer_from_snapshot(
        snapshot_dir=tmp_path, slug="pi-thing", upstream=None,
    )
    assert proposal.kind == "pi-extension"
    assert proposal.harnesses == ["pi"]


# ---------------------------------------------------------------------------
# `new` scaffold
# ---------------------------------------------------------------------------


def test_new_pi_extension_scaffolds_with_pi_harness(tmp_path):
    (tmp_path / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["new", "pi-extension", "demo-ext", "--toolkit-repo", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output

    manifest = tmp_path / "extensions" / "demo-ext" / "extension.meta.yaml"
    assert manifest.exists()
    text = manifest.read_text()
    assert "name: demo-ext" in text
    assert "- pi" in text
    assert "- claude" not in text


# ---------------------------------------------------------------------------
# End-to-end link → projection → directory symlink
# ---------------------------------------------------------------------------


def test_link_user_pi_creates_directory_symlink_for_pi_extension(env, seed_pi_extension):
    home = env["home"]
    toolkit = env["toolkit_root"]
    ext_dir = seed_pi_extension(toolkit, "status-bar", ["pi"])
    (home / ".agent-toolkit.yaml").write_text("pi_extensions:\n  - status-bar\n")
    (home / ".pi" / "agent").mkdir(parents=True)

    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "pi"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)

    link = home / ".pi" / "agent" / "extensions" / "status-bar"
    assert link.is_symlink(), f"expected symlink at {link}"
    # Critical: symlink targets the directory (so Pi can load index.ts), not
    # the manifest file. Regression guard for _expected_source.
    assert os.readlink(str(link)) == str(ext_dir)
    assert (link / "index.ts").exists()


def test_link_user_codex_skips_pi_extension(env, seed_pi_extension):
    """pi-extension declares harnesses=[pi] only; codex must not pick it up."""
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_pi_extension(toolkit, "status-bar", ["pi"])
    (home / ".agent-toolkit.yaml").write_text("pi_extensions:\n  - status-bar\n")

    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "codex"],
    )
    assert result.exit_code == 0
    assert not (home / ".codex" / "skills" / "status-bar").exists()


def test_unlink_removes_pi_extension_symlink_and_allowlist_entry(env, seed_pi_extension):
    home = env["home"]
    toolkit = env["toolkit_root"]
    seed_pi_extension(toolkit, "status-bar", ["pi"])
    (home / ".agent-toolkit.yaml").write_text("pi_extensions:\n  - status-bar\n")
    (home / ".pi" / "agent").mkdir(parents=True)

    runner = CliRunner()
    runner.invoke(main, ["--toolkit-repo", str(toolkit), "link", "user", "pi"])
    link = home / ".pi" / "agent" / "extensions" / "status-bar"
    assert link.is_symlink()

    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "unlink", "user", "pi", "pi-extension:status-bar"],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert not link.exists() and not link.is_symlink()
    assert read_allowlist(home / ".agent-toolkit.yaml")["pi_extensions"] == []
