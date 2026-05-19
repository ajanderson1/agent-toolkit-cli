"""Regression tests for _asset_harnesses with sidecar-only skills.

Bug: the else branch in _asset_harnesses called extract_metadata(asset_path)
directly, where asset_path is the body file (SKILL.md). For sidecar-only skills
(no inline frontmatter), this returned None, causing spec.harnesses to be
silently treated as [] and the asset to be skipped by the linker.

Fix: route through frontmatter_path() first so sidecars are resolved.
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.commands._link_lib import _asset_harnesses


def _make_sidecar_only_skill(root: Path, slug: str, harnesses: list[str]) -> Path:
    """Create a sidecar-only skill: body at skills/<slug>/SKILL.md (no frontmatter),
    metadata at skills/<slug>.toolkit.yaml with the given harnesses list.

    Returns the path to SKILL.md (the body file — what the linker passes as asset_path).
    """
    skill_dir = root / "skills" / slug
    skill_dir.mkdir(parents=True)
    body = skill_dir / "SKILL.md"
    body.write_text("# body only — no frontmatter\n")

    harnesses_yaml = "\n".join(f"    - {h}" for h in harnesses)
    sidecar = root / "skills" / f"{slug}.toolkit.yaml"
    sidecar.write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        f"metadata:\n  name: {slug}\n  description: A test skill.\n"
        "spec:\n  origin: first-party\n"
        f"  harnesses:\n{harnesses_yaml}\n"
    )
    return body


class TestAssetHarnessesSidecarSkill:
    def test_sidecar_only_skill_returns_harnesses(self, tmp_path: Path) -> None:
        """_asset_harnesses must read harnesses from the sidecar when SKILL.md has no frontmatter."""
        body_path = _make_sidecar_only_skill(tmp_path, "foo", ["claude", "gemini"])
        result = _asset_harnesses(body_path, "skill")
        assert sorted(result) == ["claude", "gemini"]

    def test_inline_frontmatter_skill_still_works(self, tmp_path: Path) -> None:
        """_asset_harnesses must still work for inline-frontmatter skills after the fix."""
        skill_dir = tmp_path / "skills" / "bar"
        skill_dir.mkdir(parents=True)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(
            "---\n"
            "apiVersion: agent-toolkit/v1alpha2\n"
            "metadata:\n  name: bar\n  description: A test skill.\n"
            "spec:\n  origin: first-party\n  harnesses:\n    - claude\n    - codex\n"
            "---\n\nbody\n"
        )
        result = _asset_harnesses(skill_path, "skill")
        assert sorted(result) == ["claude", "codex"]

    def test_sidecar_only_skill_no_harnesses_returns_empty(self, tmp_path: Path) -> None:
        """A sidecar without spec.harnesses should return an empty list, not raise."""
        skill_dir = tmp_path / "skills" / "baz"
        skill_dir.mkdir(parents=True)
        body = skill_dir / "SKILL.md"
        body.write_text("body\n")
        sidecar = tmp_path / "skills" / "baz.toolkit.yaml"
        sidecar.write_text(
            "apiVersion: agent-toolkit/v1alpha2\n"
            "metadata:\n  name: baz\n  description: A test skill.\n"
            "spec:\n  origin: first-party\n"
        )
        result = _asset_harnesses(body, "skill")
        assert result == []
