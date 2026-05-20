from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_new_skill_creates_skeleton(tmp_path):
    (tmp_path / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (tmp_path / "AGENTS.md").write_text(
        "<!-- BEGIN_AGENT_TOOLKIT:component-table -->\n"
        "<!-- END_AGENT_TOOLKIT:component-table -->\n"
        "<!-- BEGIN_AGENT_TOOLKIT:submodule-table -->\n"
        "<!-- END_AGENT_TOOLKIT:submodule-table -->\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["new", "skill", "demo-skill", "--toolkit-repo", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output

    # Default creates sidecar form: body file + .toolkit.yaml sidecar
    skill_md = tmp_path / "skills" / "demo-skill" / "SKILL.md"
    sidecar = tmp_path / "skills" / "demo-skill.toolkit.yaml"
    assert skill_md.exists()
    assert sidecar.exists()
    # Body now carries harness frontmatter (name + description only, not sidecar shape)
    body_text = skill_md.read_text()
    assert body_text.startswith("---\n")
    # Sidecar carries the metadata
    sidecar_text = sidecar.read_text()
    assert "apiVersion: agent-toolkit/v1alpha2" in sidecar_text
    assert "name: demo-skill" in sidecar_text
    assert "harnesses:" in sidecar_text


def test_new_skill_validates_against_schema(tmp_path):
    (tmp_path / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())

    runner = CliRunner()
    runner.invoke(main, ["new", "skill", "demo-skill", "--toolkit-repo", str(tmp_path)])
    result = runner.invoke(main, ["check", "--toolkit-repo", str(tmp_path), "--exit-code"])
    assert result.exit_code == 0, result.output


def test_new_emits_header_and_summary_on_stderr(tmp_path):
    (tmp_path / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())

    runner = CliRunner()
    result = runner.invoke(main, ["new", "skill", "demo-skill", "--toolkit-repo", str(tmp_path)])
    assert result.exit_code == 0
    assert "Scaffolding" in result.output
    assert "agent-toolkit check" in result.output   # next-step hint
    assert "created" in result.output                # original assertion preserved


def test_new_mcp_writes_readme_and_config(tmp_path):
    """Default (sidecar) form: README.md body + .toolkit.yaml sidecar + config.json."""
    (tmp_path / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (tmp_path / ".agent-toolkit-source").write_text("")

    runner = CliRunner()
    result = runner.invoke(
        main, ["new", "mcp", "fake-mcp", "--toolkit-repo", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    readme = tmp_path / "mcps" / "fake-mcp" / "README.md"
    config = tmp_path / "mcps" / "fake-mcp" / "config.json"
    sidecar = tmp_path / "mcps" / "fake-mcp.toolkit.yaml"
    assert readme.is_file()
    assert config.is_file()
    assert sidecar.is_file()
    # Body README should NOT have inline frontmatter
    assert not readme.read_text().startswith("---\n")
    # Sidecar carries the metadata
    sidecar_text = sidecar.read_text()
    assert "agent-toolkit/v1alpha2" in sidecar_text
    assert "spec:" in sidecar_text and "mcp:" in sidecar_text
    assert '"command": "npx"' in config.read_text()


def test_new_mcp_inline_flag_uses_inline_form(tmp_path):
    """--inline flag keeps frontmatter in README.md (legacy behavior)."""
    (tmp_path / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (tmp_path / ".agent-toolkit-source").write_text("")

    runner = CliRunner()
    result = runner.invoke(
        main, ["new", "mcp", "fake-mcp", "--toolkit-repo", str(tmp_path), "--inline"]
    )
    assert result.exit_code == 0, result.output
    readme = tmp_path / "mcps" / "fake-mcp" / "README.md"
    sidecar = tmp_path / "mcps" / "fake-mcp.toolkit.yaml"
    assert readme.is_file()
    assert not sidecar.exists()
    assert readme.read_text().startswith("---\n")
    assert "agent-toolkit/v1alpha2" in readme.read_text()
    assert "spec:" in readme.read_text() and "mcp:" in readme.read_text()
