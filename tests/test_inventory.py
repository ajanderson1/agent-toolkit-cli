"""Tests for the inventory library."""
from pathlib import Path

import pytest

from agent_toolkit.inventory import render_inventory, render_asset_card


def _write_skill(tmp_path: Path, slug: str, *, lifecycle: str = "stable",
                 harnesses=("claude",), description: str = None) -> None:
    description = description or f"{slug.capitalize()} skill."
    skill_dir = tmp_path / "skills" / slug
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"apiVersion: agent-toolkit/v1alpha1\n"
        f"metadata:\n"
        f"  name: {slug}\n"
        f"  description: {description}\n"
        f"  lifecycle: {lifecycle}\n"
        f"spec:\n"
        f"  origin: first-party\n"
        f"  vendored_via: none\n"
        f"  harnesses:\n"
        + "".join(f"    - {h}\n" for h in harnesses)
        + "---\n"
        "\n"
        f"# {slug}\n"
        "\n"
        f"Body of {slug}.\n"
    )


def test_render_inventory_groups_by_kind(tmp_path):
    _write_skill(tmp_path, "alpha")
    _write_skill(tmp_path, "beta")
    out = render_inventory(tmp_path, fmt="md")
    assert "## skills" in out
    assert "alpha" in out
    assert "beta" in out


def test_render_inventory_orders_stable_before_experimental(tmp_path):
    _write_skill(tmp_path, "early", lifecycle="experimental")
    _write_skill(tmp_path, "ready", lifecycle="stable")
    out = render_inventory(tmp_path, fmt="md")
    assert out.index("ready") < out.index("early")


def test_render_inventory_filters_by_harness(tmp_path):
    _write_skill(tmp_path, "alpha", harnesses=("claude",))
    _write_skill(tmp_path, "pi-only", harnesses=("pi",))
    out = render_inventory(tmp_path, fmt="md", harness="pi")
    assert "pi-only" in out
    assert "alpha" not in out


def test_render_asset_card_for_skill(tmp_path):
    _write_skill(tmp_path, "alpha", description="Alpha example.")
    out = render_asset_card(tmp_path, slug="alpha")
    assert "NAME" in out
    assert "alpha — Alpha example." in out
    assert "KIND        skill" in out
    assert "HARNESSES   claude" in out
    assert "QUICKSTART" in out
    assert "bin/agent-toolkit link user claude" in out


def test_render_asset_card_unknown_slug_raises(tmp_path):
    _write_skill(tmp_path, "alpha")
    with pytest.raises(KeyError):
        render_asset_card(tmp_path, slug="ghost")


def test_render_inventory_json_format(tmp_path):
    import json
    _write_skill(tmp_path, "alpha")
    out = render_inventory(tmp_path, fmt="json")
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert any(item["slug"] == "alpha" for item in parsed)
