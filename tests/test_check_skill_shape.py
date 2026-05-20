"""`check` enforces SKILL.md frontmatter, both descriptions, period rule, name agreement.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.schema import Validator
from agent_toolkit_cli.walker import Asset


def _write_new_shape_skill(
    root: Path,
    slug: str = "demo",
    *,
    skill_md_fm: str | None = None,
    sidecar: str | None = None,
) -> Asset:
    skill_dir = root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    default_fm = (
        "---\n"
        f"name: {slug}\n"
        "description: Long harness-facing description ending in a period.\n"
        "---\n"
    )
    (skill_dir / "SKILL.md").write_text((skill_md_fm if skill_md_fm is not None else default_fm) + "\nbody\n")
    default_sidecar = (
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        f"  name: {slug}\n"
        "  description: Concise CLI label.\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
    )
    (root / "skills" / f"{slug}.toolkit.yaml").write_text(
        sidecar if sidecar is not None else default_sidecar
    )
    return Asset(kind="skill", slug=slug, path=skill_dir / "SKILL.md")


def test_new_shape_skill_validates(tmp_path: Path):
    asset = _write_new_shape_skill(tmp_path)
    errors = Validator(toolkit_root=tmp_path).validate(asset)
    assert errors == []


def test_skill_md_missing_frontmatter_fails(tmp_path: Path):
    asset = _write_new_shape_skill(tmp_path)
    # Overwrite SKILL.md to remove frontmatter entirely
    (tmp_path / "skills" / "demo" / "SKILL.md").write_text("no frontmatter here\n")
    errors = Validator(toolkit_root=tmp_path).validate(asset)
    assert any("SKILL.md" in e and "frontmatter" in e for e in errors), errors


def test_harness_description_missing_period_fails(tmp_path: Path):
    fm = (
        "---\n"
        "name: demo\n"
        "description: No trailing period\n"
        "---\n"
    )
    asset = _write_new_shape_skill(tmp_path, skill_md_fm=fm)
    errors = Validator(toolkit_root=tmp_path).validate(asset)
    assert any("description" in e and "period" in e.lower() for e in errors), errors


def test_name_disagreement_fails(tmp_path: Path):
    fm = (
        "---\n"
        "name: not-demo\n"
        "description: Long harness description.\n"
        "---\n"
    )
    asset = _write_new_shape_skill(tmp_path, skill_md_fm=fm)
    errors = Validator(toolkit_root=tmp_path).validate(asset)
    assert any("name" in e.lower() for e in errors), errors


def test_missing_cli_description_fails(tmp_path: Path):
    bad_sidecar = (
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: demo\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
    )
    asset = _write_new_shape_skill(tmp_path, sidecar=bad_sidecar)
    errors = Validator(toolkit_root=tmp_path).validate(asset)
    # Existing schema rule fires: metadata.description required.
    assert any("description" in e for e in errors), errors


def test_legacy_inline_skill_emits_advisory_not_error(tmp_path: Path):
    # No sidecar; SKILL.md carries v1alpha2 wrapper. Tolerated by check
    # during the one-release window; doctor surfaces the advisory.
    skill_dir = tmp_path / "skills" / "legacy"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: legacy\n"
        "  description: Legacy description.\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "---\n"
        "\nbody\n"
    )
    asset = Asset(kind="skill", slug="legacy", path=skill_dir / "SKILL.md")
    errors = Validator(toolkit_root=tmp_path).validate(asset)
    # No error during tolerance window. Note: an advisory will be surfaced
    # by doctor (Task 7), not check.
    assert errors == [], errors
