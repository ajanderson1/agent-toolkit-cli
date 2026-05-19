"""Tests for sidecar metadata discovery (skill + mcp)."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.walker import (
    Asset,
    BothMetadataLocationsExist,
    _sidecar_path,
    discover_assets,
    load_asset_record,
    read_sidecar,
    resolve_metadata,
)


class TestIsToolkitFrontmatter:
    def test_toolkit_shape_returns_true(self) -> None:
        from agent_toolkit_cli.walker import is_toolkit_frontmatter
        assert is_toolkit_frontmatter({"apiVersion": "agent-toolkit/v1alpha2"})

    def test_upstream_shape_returns_false(self) -> None:
        """Upstream agentskills.io style: name + description, no apiVersion."""
        from agent_toolkit_cli.walker import is_toolkit_frontmatter
        assert not is_toolkit_frontmatter({"name": "deep-research", "description": "x."})

    def test_other_apiversion_returns_false(self) -> None:
        from agent_toolkit_cli.walker import is_toolkit_frontmatter
        assert not is_toolkit_frontmatter({"apiVersion": "v1"})

    def test_none_returns_false(self) -> None:
        from agent_toolkit_cli.walker import is_toolkit_frontmatter
        assert not is_toolkit_frontmatter(None)

    def test_non_dict_returns_false(self) -> None:
        from agent_toolkit_cli.walker import is_toolkit_frontmatter
        assert not is_toolkit_frontmatter(["just", "a", "list"])


class TestSidecarPath:
    def test_skill_sidecar_path(self, tmp_path: Path) -> None:
        result = _sidecar_path("skill", "deep-research", tmp_path)
        assert result == tmp_path / "skills" / "deep-research.toolkit.yaml"

    def test_mcp_sidecar_path(self, tmp_path: Path) -> None:
        result = _sidecar_path("mcp", "context7", tmp_path)
        assert result == tmp_path / "mcps" / "context7.toolkit.yaml"

    def test_unsupported_kind_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="sidecar not supported for kind"):
            _sidecar_path("agent", "foo", tmp_path)


class TestReadSidecar:
    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        result = read_sidecar(tmp_path / "skills" / "missing.toolkit.yaml")
        assert result is None

    def test_valid_yaml_returns_dict(self, tmp_path: Path) -> None:
        sidecar = tmp_path / "foo.toolkit.yaml"
        sidecar.write_text(
            "apiVersion: agent-toolkit/v1alpha2\n"
            "metadata:\n  name: foo\n"
            "spec:\n  origin: first-party\n"
        )
        result = read_sidecar(sidecar)
        assert result == {
            "apiVersion": "agent-toolkit/v1alpha2",
            "metadata": {"name": "foo"},
            "spec": {"origin": "first-party"},
        }

    def test_invalid_yaml_returns_none(self, tmp_path: Path) -> None:
        sidecar = tmp_path / "broken.toolkit.yaml"
        sidecar.write_text("foo: [unclosed\n")
        result = read_sidecar(sidecar)
        assert result is None

    def test_yaml_not_a_dict_returns_none(self, tmp_path: Path) -> None:
        sidecar = tmp_path / "list.toolkit.yaml"
        sidecar.write_text("- just\n- a\n- list\n")
        result = read_sidecar(sidecar)
        assert result is None

    def test_non_utf8_file_returns_none(self, tmp_path: Path) -> None:
        """Binary or non-UTF-8 content must not crash the caller."""
        sidecar = tmp_path / "binary.toolkit.yaml"
        sidecar.write_bytes(b"\xff\xfe\x00not-utf-8\xc3\x28")
        result = read_sidecar(sidecar)
        assert result is None


def _make_skill_with_inline(root: Path, slug: str) -> Path:
    """Helper: create skills/<slug>/SKILL.md with inline frontmatter."""
    skill_dir = root / "skills" / slug
    skill_dir.mkdir(parents=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        f"metadata:\n  name: {slug}\n"
        "spec:\n  origin: first-party\n"
        "---\n\nbody\n"
    )
    return skill_path


def _make_skill_with_sidecar(root: Path, slug: str) -> Path:
    """Helper: create skills/<slug>/SKILL.md (body only) + skills/<slug>.toolkit.yaml."""
    skill_dir = root / "skills" / slug
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("body\n")
    sidecar = root / "skills" / f"{slug}.toolkit.yaml"
    sidecar.write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        f"metadata:\n  name: {slug}\n"
        "spec:\n  origin: third-party\n"
    )
    return sidecar


class TestResolveMetadata:
    def test_sidecar_only(self, tmp_path: Path) -> None:
        _make_skill_with_sidecar(tmp_path, "foo")
        metadata, source = resolve_metadata("skill", "foo", tmp_path)
        assert metadata is not None
        assert metadata["metadata"]["name"] == "foo"
        assert source.name == "foo.toolkit.yaml"

    def test_inline_only(self, tmp_path: Path) -> None:
        _make_skill_with_inline(tmp_path, "bar")
        metadata, source = resolve_metadata("skill", "bar", tmp_path)
        assert metadata is not None
        assert metadata["metadata"]["name"] == "bar"
        assert source.name == "SKILL.md"

    def test_both_raises_mutex(self, tmp_path: Path) -> None:
        _make_skill_with_inline(tmp_path, "dup")
        # Now also add a sidecar at skills/dup.toolkit.yaml
        sidecar = tmp_path / "skills" / "dup.toolkit.yaml"
        sidecar.write_text(
            "apiVersion: agent-toolkit/v1alpha2\n"
            "metadata:\n  name: dup\n"
            "spec:\n  origin: third-party\n"
        )
        with pytest.raises(BothMetadataLocationsExist) as exc:
            resolve_metadata("skill", "dup", tmp_path)
        assert exc.value.slug == "dup"
        assert exc.value.kind == "skill"
        assert exc.value.sidecar_path.name == "dup.toolkit.yaml"
        assert exc.value.inline_path.name == "SKILL.md"

    def test_neither_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "skills" / "empty").mkdir(parents=True)
        (tmp_path / "skills" / "empty" / "SKILL.md").write_text("just a body\n")
        metadata, source = resolve_metadata("skill", "empty", tmp_path)
        assert metadata is None
        assert source is None


class TestDiscoverAssetsSidecar:
    def test_sidecar_skill_is_discovered(self, tmp_path: Path) -> None:
        _make_skill_with_sidecar(tmp_path, "deep-research")
        assets = discover_assets(tmp_path)
        slugs = {a.slug for a in assets if a.kind == "skill"}
        assert "deep-research" in slugs

    def test_inline_skill_still_discovered(self, tmp_path: Path) -> None:
        _make_skill_with_inline(tmp_path, "agent-toolkit")
        assets = discover_assets(tmp_path)
        slugs = {a.slug for a in assets if a.kind == "skill"}
        assert "agent-toolkit" in slugs

    def test_orphan_sidecar_not_discovered(self, tmp_path: Path) -> None:
        # Sidecar exists but body directory does not — should NOT yield an Asset
        # (this gets surfaced by check, not walker).
        (tmp_path / "skills").mkdir()
        sidecar = tmp_path / "skills" / "orphan.toolkit.yaml"
        sidecar.write_text(
            "apiVersion: agent-toolkit/v1alpha2\n"
            "metadata:\n  name: orphan\n"
            "spec:\n  origin: third-party\n"
        )
        assets = discover_assets(tmp_path)
        slugs = {a.slug for a in assets if a.kind == "skill"}
        assert "orphan" not in slugs

    def test_load_asset_record_reads_sidecar_metadata(self, tmp_path: Path) -> None:
        """Regression: load_asset_record must read metadata from sidecar.

        Was a bug where extract_frontmatter (which requires ---) was called
        on bare-YAML sidecars, silently dropping metadata.
        """
        _make_skill_with_sidecar(tmp_path, "ssot")
        assets = [a for a in discover_assets(tmp_path) if a.slug == "ssot"]
        assert len(assets) == 1
        record = load_asset_record(assets[0])
        assert record.metadata != {}
        assert record.metadata.get("metadata", {}).get("name") == "ssot"
        assert record.metadata.get("spec", {}).get("origin") == "third-party"

    def test_sidecar_for_submoduled_body(self, tmp_path: Path) -> None:
        """The point of the whole feature: sidecar outside submodule path."""
        skill_dir = tmp_path / "skills" / "vendored"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("upstream body, no frontmatter\n")
        # Pretend this directory is submoduled
        (tmp_path / ".gitmodules").write_text(
            '[submodule "skills/vendored"]\n'
            "    path = skills/vendored\n"
            "    url = https://example.com/upstream.git\n"
        )
        # Sidecar lives OUTSIDE the submoduled directory
        sidecar = tmp_path / "skills" / "vendored.toolkit.yaml"
        sidecar.write_text(
            "apiVersion: agent-toolkit/v1alpha2\n"
            "metadata:\n  name: vendored\n"
            "spec:\n  origin: third-party\n  vendored_via: submodule\n"
        )
        assets = discover_assets(tmp_path)
        slugs = {a.slug for a in assets if a.kind == "skill"}
        assert "vendored" in slugs
