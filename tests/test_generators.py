from pathlib import Path

from agent_toolkit_cli.generators.component_table import render_component_table
from agent_toolkit_cli.walker import Asset


def test_renders_component_table_sorted_by_kind(tmp_path):
    assets = [
        Asset(kind="skill", slug="alpha", path=tmp_path / "a"),
        Asset(kind="skill", slug="beta", path=tmp_path / "b"),
        Asset(kind="agent", slug="gamma", path=tmp_path / "c"),
        Asset(kind="mcp", slug="delta", path=tmp_path / "d"),
    ]
    metadata = {
        ("skill", "alpha"): {"spec": {"origin": "first-party"}},
        ("skill", "beta"): {"spec": {"origin": "third-party"}},
        ("agent", "gamma"): {"spec": {"origin": "first-party"}},
        ("mcp", "delta"): {"spec": {"origin": "first-party"}},
    }

    out = render_component_table(assets, metadata)
    lines = out.splitlines()
    # Header + separator + 3 data rows (one per kind, alphabetical kind order)
    assert lines[0].startswith("| Category")
    assert "Agents" in out
    assert "Skills" in out
    assert "MCPs" in out
    # Origin breakdown shows correct counts
    assert "1 first-party" in out  # Agents
    assert "1 first-party · 1 third-party" in out  # Skills


from agent_toolkit_cli.generators.submodule_table import render_submodule_table


def test_renders_submodule_table_from_gitmodules(tmp_path):
    gitmodules = tmp_path / ".gitmodules"
    gitmodules.write_text(
        '[submodule "skills/third_party/deep-research"]\n'
        '\tpath = skills/third_party/deep-research\n'
        '\turl = https://github.com/199-biotechnologies/claude-deep-research-skill.git\n'
        '[submodule "mcps/third_party/google-workspace"]\n'
        '\tpath = mcps/third_party/google-workspace\n'
        '\turl = git@github.com:ajanderson1/google_workspace_mcp.git\n'
    )

    out = render_submodule_table(tmp_path)
    assert "skills/third_party/deep-research" in out
    assert "199-biotechnologies/claude-deep-research-skill" in out
    assert "ajanderson1/google_workspace_mcp" in out
    assert "| Submodule path |" in out


from agent_toolkit_cli.generators.markers import inject_region


def test_inject_region_replaces_existing_block():
    src = (
        "# Header\n"
        "\n"
        "<!-- BEGIN_AGENT_TOOLKIT:component-table -->\n"
        "OLD CONTENT\n"
        "<!-- END_AGENT_TOOLKIT:component-table -->\n"
        "\n"
        "## Footer\n"
    )
    out = inject_region(src, region="component-table", body="| new |\n")
    assert "OLD CONTENT" not in out
    assert "| new |" in out
    assert "<!-- BEGIN_AGENT_TOOLKIT:component-table" in out
    assert "<!-- END_AGENT_TOOLKIT:component-table -->" in out
    assert out.startswith("# Header\n")
    assert out.rstrip().endswith("## Footer")


def test_inject_region_idempotent():
    src = (
        "<!-- BEGIN_AGENT_TOOLKIT:component-table -->\n"
        "X\n"
        "<!-- END_AGENT_TOOLKIT:component-table -->\n"
    )
    once = inject_region(src, region="component-table", body="X\n")
    twice = inject_region(once, region="component-table", body="X\n")
    assert once == twice


def test_inject_region_raises_when_markers_missing():
    src = "# Doc with no markers\n"
    import pytest
    with pytest.raises(ValueError, match="component-table"):
        inject_region(src, region="component-table", body="X\n")
