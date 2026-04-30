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


def _write_agent(tmp_path: Path, slug: str, *, harnesses=("claude",)) -> None:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(exist_ok=True)
    (agents_dir / f"{slug}.md").write_text(
        "---\n"
        f"apiVersion: agent-toolkit/v1alpha1\n"
        f"metadata:\n"
        f"  name: {slug}\n"
        f"  description: {slug.capitalize()} agent.\n"
        f"  lifecycle: stable\n"
        f"spec:\n"
        f"  origin: first-party\n"
        f"  vendored_via: none\n"
        f"  harnesses:\n"
        + "".join(f"    - {h}\n" for h in harnesses)
        + "---\n# x\n"
    )


def test_render_inventory_filters_by_kind(tmp_path):
    _write_skill(tmp_path, "alpha")
    _write_agent(tmp_path, "beta")
    out = render_inventory(tmp_path, fmt="md", kind="agent")
    assert "beta" in out
    assert "alpha" not in out


def test_render_inventory_filters_by_lifecycle(tmp_path):
    _write_skill(tmp_path, "stable-one", lifecycle="stable")
    _write_skill(tmp_path, "exp-one", lifecycle="experimental")
    out = render_inventory(tmp_path, fmt="md", lifecycle="experimental")
    assert "exp-one" in out
    assert "stable-one" not in out


def test_render_inventory_filters_by_origin(tmp_path):
    # Both fixtures default to first-party; assert that filter narrows correctly
    _write_skill(tmp_path, "alpha")
    out_first = render_inventory(tmp_path, fmt="md", origin="first-party")
    out_third = render_inventory(tmp_path, fmt="md", origin="third-party")
    assert "alpha" in out_first
    assert "alpha" not in out_third


def test_render_inventory_empty_result(tmp_path):
    _write_skill(tmp_path, "alpha", harnesses=("claude",))
    out = render_inventory(tmp_path, fmt="md", harness="codex")
    assert out == "(no assets matched)\n"


def test_render_inventory_json_includes_all_fields(tmp_path):
    import json
    _write_skill(tmp_path, "alpha")
    out = render_inventory(tmp_path, fmt="json")
    parsed = json.loads(out)
    assert parsed, "expected at least one entry"
    expected = {"slug", "kind", "lifecycle", "origin", "harnesses",
                "location", "keywords", "description", "body_excerpt"}
    assert set(parsed[0].keys()) == expected


def test_render_asset_card_includes_body_excerpt(tmp_path):
    _write_skill(tmp_path, "alpha", description="Alpha example.")
    out = render_asset_card(tmp_path, slug="alpha")
    # The fixture body is "Body of alpha." (after the heading)
    assert "Body of alpha." in out


def test_render_asset_card_lists_other_harnesses(tmp_path):
    _write_skill(tmp_path, "multi", harnesses=("claude", "codex", "pi"))
    out = render_asset_card(tmp_path, slug="multi")
    assert "Other harnesses supported: codex, pi" in out


def test_inventory_cli_full_mode(tmp_path):
    from click.testing import CliRunner
    from agent_toolkit.cli import main
    _write_skill(tmp_path, "alpha")
    runner = CliRunner()
    result = runner.invoke(main, ["inventory", "--repo-root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "alpha" in result.output


def test_inventory_cli_kind_filter(tmp_path):
    from click.testing import CliRunner
    from agent_toolkit.cli import main
    _write_skill(tmp_path, "alpha")
    runner = CliRunner()
    result = runner.invoke(main, ["inventory", "skill", "--repo-root", str(tmp_path)])
    assert result.exit_code == 0
    assert "alpha" in result.output


def test_inventory_cli_slug_zoom(tmp_path):
    from click.testing import CliRunner
    from agent_toolkit.cli import main
    _write_skill(tmp_path, "alpha", description="Alpha example.")
    runner = CliRunner()
    result = runner.invoke(main, ["inventory", "alpha", "--repo-root", str(tmp_path)])
    assert result.exit_code == 0
    assert "alpha — Alpha example." in result.output
    assert "QUICKSTART" in result.output


def test_inventory_cli_unknown_slug_exits_nonzero(tmp_path):
    from click.testing import CliRunner
    from agent_toolkit.cli import main
    _write_skill(tmp_path, "alpha")
    runner = CliRunner()
    result = runner.invoke(main, ["inventory", "ghost", "--repo-root", str(tmp_path)])
    assert result.exit_code != 0
