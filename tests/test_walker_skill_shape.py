"""AssetRecord exposes harness_description (SKILL.md) and cli_description (sidecar).

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.walker import Asset, load_asset_record


@pytest.fixture
def new_shape_skill(tmp_path: Path) -> Asset:
    root = tmp_path
    skill_dir = root / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo\n"
        "description: Long, trigger-rich harness-facing description ending in a period.\n"
        "---\n"
        "\nbody\n"
    )
    (root / "skills" / "demo.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: demo\n"
        "  description: Concise CLI label.\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude, pi]\n"
    )
    return Asset(kind="skill", slug="demo", path=skill_dir / "SKILL.md")


@pytest.fixture
def legacy_inline_skill(tmp_path: Path) -> Asset:
    root = tmp_path
    skill_dir = root / "skills" / "legacy"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: legacy\n"
        "  description: Legacy combined description.\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "---\n"
        "\nbody\n"
    )
    return Asset(kind="skill", slug="legacy", path=skill_dir / "SKILL.md")


def test_new_shape_exposes_both_descriptions(new_shape_skill: Asset):
    record = load_asset_record(new_shape_skill)
    assert record.harness_description == (
        "Long, trigger-rich harness-facing description ending in a period."
    )
    assert record.cli_description == "Concise CLI label."


def test_legacy_inline_skill_falls_back(legacy_inline_skill: Asset):
    record = load_asset_record(legacy_inline_skill)
    # Inline-only skills have no sidecar; the legacy description fills both
    # slots so consumers keep working during the tolerance window.
    assert record.harness_description == "Legacy combined description."
    assert record.cli_description == "Legacy combined description."
